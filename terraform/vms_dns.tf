locals {
  hosts = [
    { name = "pve",       ip = "192.168.1.100", local = true },
    { name = "media",     ip = "192.168.1.101", local = true },
    { name = "infra",     ip = "192.168.1.102", local = true },
    { name = "database",  ip = "192.168.1.103", local = true },
    { name = "minecraft", ip = "192.168.1.105", local = true },
    { name = "tools",     ip = "192.168.1.107", local = true },
    { name = "tailscale", ip = "192.168.1.108", local = true },
    { name = "authelia",  ip = "192.168.1.109", local = true },
    { name = "racknerd",  ip = "204.152.223.118", local = false }
  ]
}

resource "cloudflare_dns_record" "ssh_hosts" {
  for_each = { for h in local.hosts : h.name => h }

  zone_id = var.cloudflare_zone_id
  name    = each.value.local ? "${each.value.name}.local" : each.value.name
  type    = "A"
  content = each.value.ip
  ttl     = 1
  proxied = false
}
