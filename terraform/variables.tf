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

variable "pm_tls_insecure" {
  description = "Set to true to skip TLS verification (only use in lab/test)."
  type        = bool
  default     = true
}

variable "ssh_pub_key_path" {
  description = "Absolute path to the SSH public key to inject into each LXC (e.g. '~/.ssh/id_rsa.pub')"
  type        = string
}

variable "ssh_user" {
  description = "Username Ansible will connect as inside the LXC (must exist in the container, e.g. 'root' or another sudoer)."
  type        = string
  default     = "root"
}

variable "ansible_playbook_path" {
  description = "Relative path from the Terraform folder to the Ansible playbook you want to run (e.g. '../ansible/proxmox_setup.yml')."
  type        = string
  default     = "../ansible/proxmox_setup.yml"
}

variable "ansible_inventory_out" {
  description = "Filename (in this folder) where Terraform writes the generated inventory."
  type        = string
  default     = "inventory.ini"
}

# Cloudflare variables
variable "cloudflare_email" {
  description = "Cloudflare account email."
  type        = string
}

variable "cloudflare_api_key" {
  description = "Cloudflare API key with permissions to manage DNS records."
  type        = string
  sensitive   = true
}

variable "cloudflare_zone_id" {
  description = "Cloudflare zone ID for the domain you want to manage."
  type        = string
}

variable "racknerd_v0_ip" {
  description = "RackNerd v0 IP address to be used in the DNS record."
  type        = string
}