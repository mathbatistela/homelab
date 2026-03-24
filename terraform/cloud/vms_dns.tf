locals {
  network = jsondecode(file("${path.module}/../../config/network.json"))

  hosts = concat(
    [for name, ip in local.network.local_hosts : { name = name, ip = ip, local = true }],
    [for name, ip in local.network.remote_hosts : { name = name, ip = ip, local = false }]
  )
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
