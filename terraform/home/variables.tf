variable "pm_api_url" {
  description = "Proxmox API URL (e.g. https://proxmox.example.local:8006/api2/json)"
  type        = string
}

variable "pm_user" {
  description = "Proxmox API username (e.g. root@pam)"
  type        = string
}

variable "pm_password" {
  description = "Proxmox API password"
  type        = string
  sensitive   = true
}

variable "pm_tls_insecure" {
  description = "Set to true to skip TLS verification (only use in lab/test)."
  type        = bool
  default     = true
}

variable "vm_storage" {
  description = "Proxmox storage where the LXC rootfs will be created (e.g. 'local-lvm' or 'iac-vmdisks')."
  type        = string
  default     = "iac-vmdisks"
}

variable "pve_node" {
  description = "Proxmox node where the LXC will be created (e.g. 'm0')."
  type        = string
  default     = "m0"
}

variable "lxc_root_password" {
  description = "Root password for the LXC containers (must be at least 8 characters long)."
  type        = string
  sensitive   = true
}

variable "ssh_pub_key_path" {
  description = "Absolute path to the SSH public key to inject into each LXC (e.g. '~/.ssh/id_rsa.pub')"
  type        = string
}

variable "lxc_ostemplate" {
  description = "Proxmox storage and template path for LXC containers."
  type        = string
  default     = "iac-lxc-templates:vztmpl/debian-12-standard_12.7-1_amd64.tar.zst"
}

variable "lxc_network_bridge" {
  description = "Proxmox network bridge for LXC containers."
  type        = string
  default     = "vmbr0"
}

variable "lxc_network_interface" {
  description = "Network interface name inside LXC containers."
  type        = string
  default     = "eth0"
}
