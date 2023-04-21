#!/usr/bin/env python3
"""
Linode API client.

See https://www.linode.com/docs/api/.
"""
from typing import Optional
from urllib.parse import quote, urljoin

import requests


class LinodeObjectStorageClient:
    """
    Object Storage Client.

    See https://www.linode.com/docs/api/object-storage/.
    """

    def __init__(self, token: str, linode_api: str):
        self.http = requests.Session()
        self.http.auth = BearerAuth(token)
        self.linode_api = linode_api

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.http.close()

    def buckets(self):
        r = self.http.get(
            urljoin(self.linode_api, "v4/object-storage/buckets/")
        )
        r.raise_for_status()

        # FIXME: Implement pagination
        response = r.json()
        return response["data"]

    def create_object_url(
        self,
        cluster: str,
        bucket: str,
        name: str,
        method: str = "GET",
        content_type: Optional[str] = None,
        expires_in: Optional[int] = None,
    ):
        data = {"name": name, "method": method}

        if content_type:
            data["content_type"] = content_type

        if expires_in:
            data["expires_in"] = str(expires_in)

        url = urljoin(
            self.linode_api,
            f"v4/object-storage/buckets/{quote(cluster)}/{quote(bucket)}\
                /object-url",
        )

        r = self.http.post(url, json=data)
        r.raise_for_status()

        response = r.json()
        return response["url"]

    def update_object_acl(
        self, cluster: str, bucket: str, name: str, acl: str
    ):
        data = {"name": name, "acl": acl}

        url = urljoin(
            self.linode_api,
            f"https://api.linode.com/v4/object-storage/buckets/{quote(cluster)}\
                /{quote(bucket)}/object-acl",
        )
        r = self.http.put(url, json=data)
        r.raise_for_status()

        response = r.json()
        return response

    def check_ssl_exists(self, cluster: str, bucket: str) -> bool:
        url = urljoin(
            self.linode_api,
            f"https://api.linode.com/v4/object-storage/buckets/{quote(cluster)}\
                /{quote(bucket)}/ssl",
        )
        r = self.http.get(url)
        r.raise_for_status()

        response = r.json()

        if "ssl" not in response:
            return False

        return response.key("ssl")

    def upload_ssl(
        self, cluster: str, bucket: str, certificate: str, private_key: str
    ):
        data = {"certificate": certificate, "private_key": private_key}

        url = urljoin(
            self.linode_api,
            f"https://api.linode.com/v4/object-storage/buckets/{quote(cluster)}\
                /{quote(bucket)}/ssl",
        )
        r = self.http.post(url, json=data)
        r.raise_for_status()

    def delete_ssl(self, cluster: str, bucket: str):
        url = urljoin(
            self.linode_api,
            f"https://api.linode.com/v4/object-storage/buckets/{quote(cluster)}\
                /{quote(bucket)}/ssl",
        )
        r = self.http.delete(url)
        r.raise_for_status()


class BearerAuth(requests.auth.AuthBase):
    def __init__(self, token):
        self.token = token

    def __call__(self, r):
        r.headers["Authorization"] = f"Bearer {self.token}"
        return r
