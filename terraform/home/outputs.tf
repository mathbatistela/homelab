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

output "database_server" {
  description = "Attributes of the database-server LXC"
  value = {
    vmid     = proxmox_lxc.database_server.vmid
    hostname = proxmox_lxc.database_server.hostname
    ip       = proxmox_lxc.database_server.network[0].ip
  }
}

output "minecraft_server" {
  description = "Attributes of the minecraft-server LXC"
  value = {
    vmid     = proxmox_lxc.minecraft_server.vmid
    hostname = proxmox_lxc.minecraft_server.hostname
    ip       = proxmox_lxc.minecraft_server.network[0].ip
  }
}

output "tools_server" {
  description = "Attributes of the tools-server LXC"
  value = {
    vmid     = proxmox_lxc.tools_server.vmid
    hostname = proxmox_lxc.tools_server.hostname
    ip       = proxmox_lxc.tools_server.network[0].ip
  }
}

output "tailscale_server" {
  description = "Attributes of the tailscale-server LXC"
  value = {
    vmid     = proxmox_lxc.tailscale_server.vmid
    hostname = proxmox_lxc.tailscale_server.hostname
    ip       = proxmox_lxc.tailscale_server.network[0].ip
  }
}
