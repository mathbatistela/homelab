locals {
  master_ip = "${local.local_network_ip}.130/24"
  worker_ips = [
    "${local.local_network_ip}.131/24",
    "${local.local_network_ip}.132/24",
  ]
}

resource "random_password" "cluster_vms_password" {
  length           = 16
  override_special = "_%@"
  special          = true
}

resource "random_integer" "vm_id" {
  min = 100
  max = 200
}

resource "tls_private_key" "cluster_vms_key" {
  algorithm = "RSA"
  rsa_bits  = 2048
}

resource "local_sensitive_file" "cluster_vms_key_private_pem_file" {
  filename             = pathexpand("./data/ssh_keys/k3s-cluster-private.pem")
  file_permission      = "600"
  directory_permission = "700"
  content              = tls_private_key.cluster_vms_key.private_key_pem
}

resource "local_file" "cluster_vms_key_public_pem_file" {
  filename = pathexpand("./data/ssh_keys/k3s-cluster-public.pem")
  content  = tls_private_key.cluster_vms_key.public_key_openssh
}

resource "proxmox_virtual_environment_vm" "master_vm" {
  name        = "k3s-cluster-master"
  description = "K3s Cluster Master"
  tags        = ["ubuntu", "k3s", "master"]

  node_name = local.proxmox_node_name
  vm_id     = random_integer.vm_id.result

  cpu {
    cores        = 2
    architecture = "x86_64"
  }

  memory {
    dedicated = 2048
  }

  disk {
    datastore_id = "local-sata"
    file_id      = proxmox_virtual_environment_file.latest_ubuntu_22_jammy_img.id
    interface    = "scsi0"
    size         = 10
    ssd          = true
  }

  initialization {

    ip_config {
      ipv4 {
        address = local.master_ip
      }
    }

    user_account {
      keys     = [trimspace(tls_private_key.cluster_vms_key.public_key_openssh)]
      password = random_password.cluster_vms_password.result
      username = "ubuntu"
    }
  }

  network_device {
    bridge = "vmbr0"
  }

  tpm_state {
    version = "v2.0"
  }

  operating_system {
    type = "l26"
  }

}

resource "proxmox_virtual_environment_vm" "worker_vm" {
  count = length(local.worker_ips)

  name        = "k3s-cluster-worker-${count.index + 1}"
  description = "K3s cluster worker node"
  tags        = ["ubuntu", "k3s", "worker"]

  node_name = local.proxmox_node_name
  vm_id     = random_integer.vm_id.result + count.index + 1

  cpu {
    cores        = 2
    architecture = "x86_64"
  }

  memory {
    dedicated = 2048
  }

  disk {
    datastore_id = "local-sata"
    file_id      = proxmox_virtual_environment_file.latest_ubuntu_22_jammy_img.id
    interface    = "scsi0"
    size         = 10
    ssd          = true
  }

  initialization {
    ip_config {
      ipv4 {
        address = element(local.worker_ips, count.index)
      }
    }

    user_account {
      keys     = [trimspace(tls_private_key.cluster_vms_key.public_key_openssh)]
      password = random_password.cluster_vms_password.result
      username = "ubuntu"
    }
  }

  network_device {
    bridge = "vmbr0"
  }

  tpm_state {
    version = "v2.0"
  }

  operating_system {
    type = "l26"
  }
}

output "master_vm_id" {
  value = proxmox_virtual_environment_vm.master_vm.id
}

output "master_vm_ipv4_addresses" {
  value = "${local.local_network_ip}.${random_integer.vm_id.result}/24"
}

output "worker_vm_ids" {
  description = "IDs of the created worker VMs"
  value       = [for vm in proxmox_virtual_environment_vm.worker_vm : vm.id]
}

output "worker_vm_ips" {
  description = "IP addresses of the created worker VMs"
  value       = [for idx, ip in local.worker_ips : { "name" = proxmox_virtual_environment_vm.worker_vm[idx].name, "ip" = ip }]
}

output "cluster_vm_passwords" {
  value     = random_password.cluster_vms_password.result
  sensitive = true
}