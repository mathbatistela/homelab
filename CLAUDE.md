# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a homelab infrastructure-as-code repository that manages a Proxmox-based virtualized environment using Terraform and Ansible. The infrastructure consists of multiple LXC containers running various services (media server, database server, monitoring, etc.) on a local network (192.168.1.0/24).

## Architecture

### Two-Layer Infrastructure Management

1. **Terraform Layer** (`terraform/`): Infrastructure provisioning, split into:
   - `terraform/home/`: Proxmox LXC containers for local homelab
   - `terraform/cloud/`: Cloudflare DNS + AWS resources
2. **Ansible Layer** (`ansible/`): Configures and manages services within the provisioned containers

### Virtual Machine Architecture

The homelab consists of several LXC containers, each serving specific purposes:

- **pve** (192.168.1.100): Proxmox VE host node
- **media** (192.168.1.101): Media services (*arr stack, Samba shares)
- **infra** (192.168.1.102): Infrastructure services (Traefik reverse proxy, CheckMK monitoring)
- **database** (192.168.1.103): Database services (PostgreSQL, Redis, InfluxDB)
- **minecraft** (192.168.1.105): Minecraft game server
- **tools** (192.168.1.107): General purpose tools server
- **tailscale** (192.168.1.108): VPN gateway

All containers use Debian 12 as the base OS template.

### Ansible Structure

Ansible configuration follows a multi-inventory structure:
- **Inventories**: `ansible/inventories/local/` (main environment) and `ansible/inventories/cloud/`
- **Playbooks**: Organized by target type in `ansible/playbooks/vms/` and `ansible/playbooks/nodes/`
- **Roles**: Custom roles in `ansible/roles/` plus external collections (geerlingguy, checkmk)
- **Vault**: Encrypted secrets stored in `vault.yml` files, unlocked via `vault.auth`

Key design pattern: Playbooks in `ansible/playbooks/vms/` correspond to specific VMs and orchestrate multiple roles to configure each system end-to-end.

## Essential Commands

### Terraform Operations

The terraform configuration is split into two modules:

**Home (Proxmox LXC containers):**
```bash
cd terraform/home

tofu init           # Initialize
tofu plan           # Plan changes
tofu apply          # Apply changes
```

**Cloud (Cloudflare DNS + AWS):**
```bash
cd terraform/cloud

tofu init           # Initialize
tofu plan           # Plan changes
tofu apply          # Apply changes
```

**Important**: Each module has its own state file and `terraform.tfvars` (git-ignored). Always run commands from within the specific module directory.

### Ansible Operations

```bash
cd ansible

# Install required collections and roles
ansible-galaxy collection install -r requirements.yml

# Run a specific playbook
ansible-playbook playbooks/vms/infra.yml
ansible-playbook playbooks/vms/database.yml
ansible-playbook playbooks/vms/media.yml

# Run with specific tags
ansible-playbook playbooks/vms/database.yml --tags postgresql_install
ansible-playbook playbooks/vms/infra.yml --tags checkmk_server

# Run playbook for specific host
ansible-playbook playbooks/vms/infra.yml --limit infra

# List hosts in inventory
ansible-inventory --list

# Check connectivity to all hosts
ansible all -m ping

# Run ad-hoc command on all hosts
ansible all -a "uptime"
```

**Important**: The default inventory is set to `ansible/inventories/` which includes both `local/` and `cloud/`. Vault password is automatically loaded from `vault.auth`.

### Working with Ansible Vault

```bash
cd ansible

# Edit encrypted vault file
ansible-vault edit inventories/local/group_vars/all/vault.yml

# View encrypted vault file
ansible-vault view inventories/local/group_vars/all/vault.yml

# Encrypt a new file
ansible-vault encrypt inventories/local/group_vars/all/vault.yml

# Change vault password
ansible-vault rekey inventories/local/group_vars/all/vault.yml
```

**Note**: The vault password file (`vault.auth`) is git-ignored and must exist for Ansible to decrypt vault files.

## Key Configuration Patterns

### Adding a New VM

1. Add Terraform resource in `terraform/home/main.tf` following the existing pattern
2. Add corresponding DNS entry in `terraform/cloud/vms_dns.tf` locals
3. Add host to `ansible/inventories/local/hosts.yml`
4. Create playbook in `ansible/playbooks/vms/<hostname>.yml`
5. Apply: `cd terraform/home && tofu apply`, then `cd terraform/cloud && tofu apply`, then `ansible-playbook playbooks/vms/<hostname>.yml`

### Adding a New Ansible Role

1. Create role structure: `ansible/roles/<role_name>/{tasks,defaults,handlers,files,templates}/`
2. Define tasks in `tasks/main.yml`
3. Set defaults in `defaults/main.yml`
4. Reference role in appropriate playbook

### Service Configuration with Traefik

Services on the `infra` host are exposed via Traefik reverse proxy. There are two ways to configure services:

**Method 1: Template-based configuration (recommended for simple services)**

```yaml
- name: Add service config
  include_role:
    name: traefik
    tasks_from: configure_service
  vars:
    traefik_conf:
      template: simple-http  # or 'with-middleware' or 'tcp-service'
      service_name: myapp
      service_host: myapp.local.batistela.tech
      service_backend_url: http://localhost:8080
```

Available templates in `ansible/roles/traefik/templates/services/`:
- `simple-http`: Basic HTTP service with TLS (most common)
- `with-middleware`: HTTP service with custom middlewares (auth, redirects)
- `tcp-service`: TCP/UDP services (databases, game servers)

**Method 2: Inline content (for complex custom configurations)**

```yaml
- name: Add service dynamic config
  include_role:
    name: traefik
    tasks_from: configure_service
  vars:
    traefik_conf:
      filename: service-name.yml
      content: |
        http:
          routers:
            service-name:
              rule: "Host(`service.{{ traefik_local_domain }}`)"
              ...

### Database Setup Pattern

The database VM hosts multiple database engines. Each application database is configured in `ansible/playbooks/vms/database.yml`:
- PostgreSQL: Users and databases defined under `postgresql_users` and `postgresql_databases`
- InfluxDB: Databases defined under `influxdb_databases`
- Redis: Installed via geerlingguy.redis role with default configuration

Credentials are stored in vault as `vault.database.<service>_user_pw`.

## Important Files

- `ansible/ansible.cfg`: Ansible configuration including vault password file location
- `ansible/requirements.yml`: External Ansible collections dependencies
- `ansible/inventories/local/hosts.yml`: Inventory defining all managed hosts
- `ansible/inventories/local/group_vars/all/vault.yml`: Encrypted secrets (git-tracked but encrypted)
- `terraform/home/`: Proxmox LXC container definitions
- `terraform/cloud/`: Cloudflare DNS + AWS resource definitions
- `terraform/*/terraform.tfvars`: Variable values (git-ignored, contains secrets)

## Network and Access

- Local network: 192.168.1.0/24
- Gateway: 192.168.1.254
- SSH access: Configured via SSH public key (path specified in Terraform variables)
- All VMs use root SSH access with key authentication (ansible_user: root, key: ~/.ssh/homelab)
- Domain: local.batistela.tech (managed via Cloudflare DNS)
