output "dns_records" {
  description = "All DNS records created for VM hosts"
  value = {
    for key, record in cloudflare_dns_record.ssh_hosts : key => {
      name    = record.name
      content = record.content
      type    = record.type
    }
  }
}
