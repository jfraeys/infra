#!/usr/bin/env python3
import contextlib
import datetime
from typing import Union, cast
from urllib.parse import quote, urlunsplit

import requests
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from . import acme_utils, docker_utils, linode_utils, log_utils


def generate_private_key(
    s3_key_size: int,
) -> rsa.RSAPrivateKeyWithSerialization:
    LOG.info("Generating %d-bit RSA private key", s3_key_size)
    private_key = rsa.generate_private_key(
        public_exponent=65537, key_size=s3_key_size
    )

    return private_key


def generate_csr(
    s3_domain: str, private_key: rsa.RSAPrivateKeyWithSerialization
) -> x509.CertificateSigningRequest:

    LOG.info("Creating CSR for %s", s3_domain)
    csr = (
        x509.CertificateSigningRequestBuilder()
        .subject_name(
            x509.Name(
                [
                    x509.NameAttribute(NameOID.COMMON_NAME, s3_domain),
                ]
            )
        )
        .add_extension(
            x509.SubjectAlternativeName(
                [
                    x509.DNSName(s3_domain),
                ]
            ),
            critical=False,
        )
        .sign(private_key, hashes.SHA256())
    )

    return csr


def registering_acme_account(
    acme_client: acme_utils.AcmeClient, acme_agree_tos: bool
) -> Union[acme_utils.Account, int]:

    LOG.info("Registering account")
    try:
        account = acme_client.new_account(
            terms_of_service_agreed=acme_agree_tos,
        )
    except requests.HTTPError as e:
        LOG.error(f"Failed to create account: {e.response.text}")
        return 1

    if not account:
        LOG.warn("Account creation returned None")
        return 1

    LOG.debug("account: %s", account)

    return account


def order_auth(
    order: acme_utils.Order,
    s3_domain: str,
    s3_cluster: str,
    s3_label: str,
    acme_supported_challenges: str,
    account: acme_utils.Account,
    object_storage: linode_utils.LinodeObjectStorageClient,
) -> int:

    LOG.info("Performing authorizations")
    for authorization in order.authorizations:
        for challenge in authorization.challenges:
            if challenge.type in acme_supported_challenges:
                break
        else:
            LOG.error(f"No supported challenges {acme_supported_challenges}")
            return 1

        # Create http-01 challenge resource
        try:
            obj_name = (
                f'/.well-known/acme-challenge/{quote(challenge["token"])}'
            )
            data = f'{challenge["token"]}.{account.key_thumbprint}'

            put_url = object_storage.create_object_url(
                s3_cluster,
                s3_label,
                obj_name,
                "PUT",
                "text/plain",
                expires_in=360,
            )

            requests.put(
                put_url, data=data, headers={"Content-Type": "text/plain"}
            ).raise_for_status()
        except requests.HTTPError as e:
            LOG.error(
                f"Failed to create challenge resource: {e.response.text}"
            )
            return 1

        try:
            # Make challenge resource publicly readable
            object_storage.update_object_acl(
                s3_cluster, s3_label, obj_name, "public-read"
            )

            # Check we can read the challenge resource
            try:
                requests.head(
                    urlunsplit(("http", s3_domain, obj_name, "", ""))
                ).raise_for_status()
            except requests.HTTPError as e:
                LOG.error(f"Failed to read challenge: {e}")
                return 1

            # Respond to the challenge
            try:
                challenge.respond()
                challenge.poll_until_not({"processing", "pending"})
            except requests.HTTPError as e:
                LOG.error(f"Responding to challenge failed: {e.response.text}")
                return 1

            if challenge.status != "valid":
                LOG.error(f"Challenge unsuccessful: {challenge.status}")
                return 1

        finally:
            # Cleanup challenge resource
            try:
                delete_url = object_storage.create_object_url(
                    s3_cluster,
                    s3_label,
                    obj_name,
                    "DELETE",
                    expires_in=360,
                )

                requests.delete(delete_url).raise_for_status()
            except requests.HTTPError as e:
                LOG.warning("Failed to cleanup challenge resource: %s", e)

    return 0


def creating_acme_order(
    s3_domain: str,
    s3_cluster: str,
    s3_label: str,
    acme_client: acme_utils.AcmeClient,
    acme_supported_challenges: str,
    account: acme_utils.Account,
    csr: x509.CertificateSigningRequest,
    object_storage: linode_utils.LinodeObjectStorageClient,
) -> Union[str, int]:

    LOG.info("Creating new order for %s", s3_domain)
    domains = [s3_domain]

    try:
        order = acme_client.new_order(domains)
    except requests.HTTPError as e:
        LOG.error(f"Failed to create order: {e.response.text}")
        return 1

    LOG.debug("order: %s", order)

    order_auth_status = order_auth(
        order,
        s3_domain,
        s3_cluster,
        s3_label,
        acme_supported_challenges,
        account,
        object_storage,
    )

    if order_auth_status == 1:
        LOG.warn("Failed authorizations to order certificate.")
        return 1

    LOG.info("Finalizing order")
    try:
        order.finalize(csr)
        order.poll_until_not({"processing"})
    except requests.HTTPError as e:
        LOG.error(f"Failed to finalize order: {e.response.text}")
        return 1

    if order.status != "valid":
        LOG.error(f"Finalize unsuccessful: {order.status}")
        return 1

    try:
        certificate = order.certificate()
    except requests.HTTPError as e:
        LOG.error(f"Failed to fetch certificate: {e.response.text}")
        return 1

    return certificate


def update_certs(
    object_storage: linode_utils.LinodeObjectStorageClient,
    s3_cluster: str,
    s3_label: str,
    private_key: rsa.RSAPrivateKeyWithSerialization,
    certificate: str,
) -> int:
    LOG.info("Updating certs")
    try:
        object_storage.delete_ssl(s3_cluster, s3_label)
    except requests.HTTPError as e:
        LOG.error(f"Failed to delete old certificate: {e.response.text}")
        return 1

    private_key_pem = private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption(),
    ).decode("ascii")

    try:
        object_storage.upload_ssl(
            s3_cluster,
            s3_label,
            certificate,
            private_key_pem,
        )
    except requests.HTTPError as e:
        LOG.error(f"Failed to create certificate: {e.response.text}")
        return 1

    return 0


def set_s3_ssl(
    s3_domain: str,
    s3_cluster: str,
    s3_label: str,
    s3_account_key_filename: str,
    s3_key_size: int,
    s3_linode_api: str,
    s3_dir_url: str,
    s3_user_agent: str,
    acme_supported_challenges: str,
    acme_agree_tos: bool = True,
    s3_secret_access_key_filename: str = "LINODE_BUCKET_ACCESS_KEY",
) -> int:
    bucket_access_key = docker_utils.get_env_secrets(
        s3_secret_access_key_filename
    )
    # abs_path = docker_utils.get_root_dir() # make sure this still works even when using hydra

    if not bucket_access_key:
        LOG.warn("Bucket access key environment secret variable not set")
        return 1

    with open(s3_account_key_filename, "rb") as f:
        account_key: rsa.RSAPrivateKeyWithSerialization = (
            serialization.load_pem_private_key(f.read(), None)
        )

    private_key = generate_private_key(s3_key_size)

    csr = generate_csr(s3_domain, private_key)

    with contextlib.ExitStack() as cleanup:
        object_storage = linode_utils.LinodeObjectStorageClient(
            bucket_access_key, s3_linode_api
        )
        cleanup.push(object_storage)

        acme_client = acme_utils.AcmeClient(s3_dir_url, account_key)
        cleanup.push(acme_client)

        object_storage.http.headers["User-Agent"] = s3_user_agent
        acme_client.http.headers["User-Agent"] = s3_user_agent

        buckets = [
            bucket
            for bucket in object_storage.buckets()
            if bucket["cluster"] == s3_cluster and bucket["label"] == s3_label
        ]

        if not buckets:
            LOG.error("No matching bucket found")
            return 1

        account = registering_acme_account(acme_client, acme_agree_tos)

        if isinstance(account, int):
            exit(account)

        certificate = creating_acme_order(
            s3_domain,
            s3_cluster,
            s3_label,
            acme_client,
            acme_supported_challenges,
            account,
            csr,
            object_storage,
        )

        if isinstance(certificate, int):
            exit(certificate)

        update_certs(
            object_storage,
            s3_cluster,
            s3_label,
            private_key,
            str(certificate),
        )

    return 0


def check_s3_ssl_is_set(
    s3_cluster: str,
    s3_bucket: str,
    s3_linode_api: str,
    s3_secret_access_key_filename: str = "LINODE_BUCKET_ACCESS_KEY",
) -> bool:
    bucket_access_key = docker_utils.get_env_secrets(
        s3_secret_access_key_filename
    )

    if not bucket_access_key:
        LOG.warn("Bucket access key environment secret variable not set")
        return False

    object_storage = linode_utils.LinodeObjectStorageClient(
        bucket_access_key, s3_linode_api
    )

    return object_storage.check_ssl_exists(s3_cluster, s3_bucket)
