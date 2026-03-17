locals {
  default_ostemplate     = "iac-lxc-templates:vztmpl/debian-12-standard_12.7-1_amd64.tar.zst"
  default_network_bridge = "vmbr0"

  servers = {
    media = {
      vmid        = 101
      hostname    = "media"
      cores       = 2
      memory      = 4096
      swap        = 1024
      disk_size   = "16G"
      ip          = "192.168.1.101/24"
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
      ip          = "192.168.1.102/24"
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
      ip          = "192.168.1.103/24"
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
      ip          = "192.168.1.105/24"
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
      ip         = "192.168.1.107/24"
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
      ip          = "192.168.1.108/24"
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
  ostemplate   = local.default_ostemplate
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
    name   = "eth0"
    bridge = local.default_network_bridge
    ip     = each.value.ip
    gw     = "192.168.1.254"
  }

  onboot  = true
  startup = "order=1,up=30,down=30"

  ssh_public_keys = file(var.ssh_pub_key_path)
  password        = var.lxc_root_password
}
