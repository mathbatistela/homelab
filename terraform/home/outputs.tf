output "servers" {
  description = "Attributes of all LXC servers"
  value = {
    for key, server in proxmox_lxc.servers : key => {
      vmid     = server.vmid
      hostname = server.hostname
      ip       = try(server.network[0].ip, "unknown")
    }
  }
}
