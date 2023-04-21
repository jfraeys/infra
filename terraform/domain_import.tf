resource "linode_domain" "jfraeys_com_domain" {
  domain    = "jfraeys.com"
  soa_email = "jfraeys@gmail.com"
  type      = "master"
}
