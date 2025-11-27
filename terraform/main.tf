locals {
  default_ostemplate     = "iac-lxc-templates:vztmpl/debian-12-standard_12.7-1_amd64.tar.zst"
  default_network_bridge = "vmbr0"
}

resource "proxmox_lxc" "media_server" {
  vmid         = 101
  hostname     = "media"
  target_node  = var.pve_node
  ostemplate   = local.default_ostemplate
  unprivileged = true

  cores  = 2
  memory = 4096
  swap   = 1024

  rootfs {
    storage = var.vm_storage
    size    = "16G"
  }

  features {
    nesting = true
  }

  network {
    name   = "eth0"
    bridge = local.default_network_bridge
    ip     = "192.168.1.101/24"
    gw     = "192.168.1.254"
  }

  onboot  = true
  startup = "order=1,up=30,down=30"

  ssh_public_keys = file(var.ssh_pub_key_path)
  password        = var.lxc_root_password
}

resource "proxmox_lxc" "infra_server" {
  vmid         = 102
  hostname     = "infra"
  target_node  = var.pve_node
  ostemplate   = local.default_ostemplate
  unprivileged = true

  cores  = 2
  memory = 4096
  swap   = 512

  rootfs {
    storage = var.vm_storage
    size    = "16G"
  }

  features {
    nesting = true
  }

  network {
    name   = "eth0"
    bridge = local.default_network_bridge
    ip     = "192.168.1.102/24"
    gw     = "192.168.1.254"
  }

  onboot  = true
  startup = "order=1,up=30,down=30"

  ssh_public_keys = file(var.ssh_pub_key_path)
  password        = var.lxc_root_password
}

resource "proxmox_lxc" "database_server" {
  vmid         = 103
  hostname     = "database"
  target_node  = var.pve_node
  ostemplate   = local.default_ostemplate
  unprivileged = true
  nameserver   = "1.1.1.1 8.8.8.8"

  cores  = 2
  memory = 4096
  swap   = 1024

  rootfs {
    storage = var.vm_storage
    size    = "32G"
  }

  features {
    nesting = true
  }

  network {
    name   = "eth0"
    bridge = local.default_network_bridge
    ip     = "192.168.1.103/24"
    gw     = "192.168.1.254"
  }

  onboot  = true
  startup = "order=1,up=30,down=30"
  ssh_public_keys = file(var.ssh_pub_key_path)
  password        = var.lxc_root_password
}

resource "proxmox_lxc" "minecraft_server" {
  vmid         = 105
  hostname     = "minecraft"
  target_node  = var.pve_node
  ostemplate   = local.default_ostemplate
  unprivileged = true

  cores  = 4
  memory = 8192
  swap   = 2048

  rootfs {
    storage = var.vm_storage
    size    = "50G"
  }

  features {
    nesting = true
  }

  network {
    name   = "eth0"
    bridge = local.default_network_bridge
    ip     = "192.168.1.105/24"
    gw     = "192.168.1.254"
  }

  onboot  = true
  startup = "order=1,up=30,down=30"

  ssh_public_keys = file(var.ssh_pub_key_path)
  password        = var.lxc_root_password
}

resource "proxmox_lxc" "tools_server" {
  vmid         = 107
  hostname     = "tools"
  target_node  = var.pve_node
  ostemplate   = local.default_ostemplate
  unprivileged = true

  cores  = 2
  memory = 8192
  swap   = 2048

  rootfs {
    storage = var.vm_storage
    size    = "50G"
  }

  mountpoint {
    key     = "mp0"
    slot    = 0
    volume  = "/mnt/homeshare"
    mp      = "/mnt/homeshare"
    backup  = false
  }

  features {
    nesting = true
  }

  network {
    name   = "eth0"
    bridge = local.default_network_bridge
    ip     = "192.168.1.107/24"
    gw     = "192.168.1.254"
  }

  onboot  = true
  startup = "order=1,up=30,down=30"
  ssh_public_keys = file(var.ssh_pub_key_path)
  password        = var.lxc_root_password
}

resource "proxmox_lxc" "tailscale_server" {
  vmid         = 108
  hostname     = "tailscale"
  target_node  = var.pve_node
  ostemplate   = local.default_ostemplate
  unprivileged = true

  cores  = 1
  memory = 512

  rootfs {
    storage = var.vm_storage
    size    = "5G"
  }

  features {
    nesting = true
  }

  network {
    name   = "eth0"
    bridge = local.default_network_bridge
    ip     = "192.168.1.108/24"
    gw     = "192.168.1.254"
  }

  onboot  = true
  startup = "order=1,up=30,down=30"
  ssh_public_keys = file(var.ssh_pub_key_path)
  password        = var.lxc_root_password
}