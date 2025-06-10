output "media_server" {
  description = "Attributes of the media-server LXC"
  value = {
    vmid     = proxmox_lxc.media_server.vmid
    hostname = proxmox_lxc.media_server.hostname
    ip       = proxmox_lxc.media_server.network[0].ip
  }
}

output "infra_server" {
  description = "Attributes of the infra-server LXC"
  value = {
    vmid     = proxmox_lxc.infra_server.vmid
    hostname = proxmox_lxc.infra_server.hostname
    ip       = proxmox_lxc.infra_server.network[0].ip
  }
}