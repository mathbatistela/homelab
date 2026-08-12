terraform {
  required_version = ">= 1.6.0"

  required_providers {
    # TODO: pinned to a release candidate. Track
    # https://github.com/Telmate/terraform-provider-proxmox/releases and move to
    # a stable 3.x pin once one is published.
    proxmox = {
      source  = "Telmate/proxmox"
      version = "3.0.2-rc07" # RC — no stable release available as of 2026-03-17
    }
  }
}

provider "proxmox" {
  pm_api_url      = var.pm_api_url
  pm_user         = var.pm_user
  pm_password     = var.pm_password
  pm_tls_insecure = var.pm_tls_insecure
}
