resource "proxmox_virtual_environment_file" "latest_ubuntu_22_jammy_img" {
  content_type = "iso"
  datastore_id = "local"
  node_name    = local.proxmox_node_name
  
  source_file {
    path = "https://cloud-images.ubuntu.com/jammy/current/jammy-server-cloudimg-amd64.img"
  }
}
