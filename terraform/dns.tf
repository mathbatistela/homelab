resource "cloudflare_dns_record" "pangolin_root" {
  zone_id = var.cloudflare_zone_id
  name    = "*"
  type    = "A"
  content   = var.racknerd_v0_ip
  ttl     = 1
  proxied = false
}

resource "cloudflare_dns_record" "pangolin_dash" {
  zone_id = var.cloudflare_zone_id
  name    = "pangolin"
  type    = "A"
  content   = var.racknerd_v0_ip
  ttl     = 1
  proxied = false
}