resource "linode_domain_record" "services_domain_record" {
  domain_id   = 1785853
  name        = "services"
  port        = 0
  priority    = 0
  record_type = "A"
  target      = "172.105.30.25"
  ttl_sec     = 0
  weight      = 0
}
