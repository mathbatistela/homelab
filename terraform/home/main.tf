locals {
  network = jsondecode(file("${path.module}/../../config/network.json"))

  servers = {
    media = {
      vmid        = 101
      hostname    = "media"
      cores       = 2
      memory      = 4096
      swap        = 1024
      disk_size   = "16G"
      ip          = "${local.network.local_hosts.media}${local.network.cidr}"
      nameserver  = null
      mountpoints = []
    }
    infra = {
      vmid        = 102
      hostname    = "infra"
      cores       = 2
      memory      = 4096
      swap        = 512
      disk_size   = "16G"
      ip          = "${local.network.local_hosts.infra}${local.network.cidr}"
      nameserver  = null
      mountpoints = []
    }
    database = {
      vmid        = 103
      hostname    = "database"
      cores       = 2
      memory      = 4096
      swap        = 1024
      disk_size   = "32G"
      ip          = "${local.network.local_hosts.database}${local.network.cidr}"
      nameserver  = "1.1.1.1 8.8.8.8"
      mountpoints = []
    }
    minecraft = {
      vmid        = 105
      hostname    = "minecraft"
      cores       = 4
      memory      = 8192
      swap        = 2048
      disk_size   = "50G"
      ip          = "${local.network.local_hosts.minecraft}${local.network.cidr}"
      nameserver  = null
      mountpoints = []
    }
    tools = {
      vmid       = 107
      hostname   = "tools"
      cores      = 2
      memory     = 8192
      swap       = 2048
      disk_size  = "50G"
      ip         = "${local.network.local_hosts.tools}${local.network.cidr}"
      nameserver = null
      mountpoints = [
        {
          key    = "mp0"
          slot   = 0
          volume = "/mnt/homeshare"
          mp     = "/mnt/homeshare"
          backup = false
        }
      ]
    }
    tailscale = {
      vmid        = 108
      hostname    = "tailscale"
      cores       = 1
      memory      = 512
      swap        = 0
      disk_size   = "5G"
      ip          = "${local.network.local_hosts.tailscale}${local.network.cidr}"
      nameserver  = null
      mountpoints = []
    }
  }
}

resource "proxmox_lxc" "servers" {
  for_each = local.servers

  vmid         = each.value.vmid
  hostname     = each.value.hostname
  target_node  = var.pve_node
  ostemplate   = var.lxc_ostemplate
  unprivileged = true
  nameserver   = each.value.nameserver != null ? each.value.nameserver : ""

  cores  = each.value.cores
  memory = each.value.memory
  swap   = each.value.swap > 0 ? each.value.swap : null

  rootfs {
    storage = var.vm_storage
    size    = each.value.disk_size
  }

  features {
    nesting = true
  }

  dynamic "mountpoint" {
    for_each = each.value.mountpoints
    content {
      key    = mountpoint.value.key
      slot   = mountpoint.value.slot
      volume = mountpoint.value.volume
      mp     = mountpoint.value.mp
      backup = mountpoint.value.backup
    }
  }

  network {
    name   = var.lxc_network_interface
    bridge = var.lxc_network_bridge
    ip     = each.value.ip
    gw     = local.network.gateway
  }

  onboot  = true
  startup = "order=1,up=30,down=30"

  ssh_public_keys = file(var.ssh_pub_key_path)
  password        = var.lxc_root_password
}
