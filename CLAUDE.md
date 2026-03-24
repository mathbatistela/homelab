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

### Sources of Truth

The repository uses centralized configuration files that are consumed by both Terraform and Ansible:

- `config/network.json`: **Single source of truth for all host IPs.** Consumed by Terraform (DNS generation), the Ansible vars plugin (auto-sets `ansible_host`), and the validation script.
- `config/domains.yml`: Shared domain/email/network settings for Ansible.
- `config/services/<host>/<service>.yml`: Declarative service manifests — define what a service is, how it's exposed, and who deploys it.
- `config/fragments/traefik/`: Traefik routing fragments for services that need custom routing (middlewares, special backends).
- `config/fragments/pangolin/`: Pangolin blueprint fragments for services that need custom public exposure.

### How IP Assignment Works

Host IPs are defined **only** in `config/network.json`. The Ansible vars plugin (`ansible/plugins/vars/network_json.py`) automatically sets `ansible_host` for any inventory host whose name matches a key in `network.json`. This means `hosts.yml` only defines group membership — no IPs.

### How Service Routing Works

Services are exposed via two systems: **Traefik** (local, on the `infra` host) and **Pangolin** (public, on RackNerd).

Each service manifest in `config/services/` declares its exposure mode per scope (local/public):

- **`mode: generated`** — Traefik/Pangolin config is auto-generated from the manifest fields (subdomain, port, protocol). Zero extra files needed.
- **`mode: fragment`** — Routing is defined in a fragment file (`config/fragments/traefik/<name>.yml` or `config/fragments/pangolin/<name>.yml`). Used when the service needs custom middleware, auth, special backends, etc.

The playbooks `infra.yml` and `pangolin.yml` load both manifests and fragments at runtime, merging them into the final routing configuration.

### Ansible Structure

Ansible configuration follows a multi-inventory structure:
- **Inventories**: `ansible/inventories/local/` (main environment) and `ansible/inventories/cloud/`
- **Playbooks**: Organized by target type in `ansible/playbooks/vms/` and `ansible/playbooks/nodes/`
- **Roles**: Custom roles in `ansible/roles/` plus external collections (geerlingguy, checkmk)
- **Plugins**: Custom vars plugin in `ansible/plugins/vars/` and callback plugin in `ansible/plugins/callbacks/`
- **Vault**: Encrypted secrets stored in `vault.yml` files, unlocked via `vault.auth`

Key design pattern: Playbooks in `ansible/playbooks/vms/` correspond to specific VMs and orchestrate multiple roles to configure each system end-to-end.

## Essential Commands

### Make Targets

```bash
# Bootstrap & health checks
make bootstrap        # Install venv + Ansible collections
make doctor           # Verify all dependencies
make lint             # Run ansible-lint
make syntax-check     # Dry-run all playbooks
make validate         # Check consistency across network.json, Terraform, inventory, manifests

# Terraform
make plan-home        # Plan Proxmox changes
make plan-cloud       # Plan Cloudflare/AWS changes
make apply-home       # Apply Proxmox changes
make apply-cloud      # Apply Cloudflare/AWS changes
make validate-home    # Validate Terraform home config
make validate-cloud   # Validate Terraform cloud config

# Ansible playbooks
make play-infra       # Traefik + service routing
make play-database    # PostgreSQL, InfluxDB, Redis
make play-media       # *arr stack, Samba
make play-minecraft   # Game server
make play-tools       # Docker, Actual Budget, Portainer
make play-monitoring  # node_exporter, cAdvisor, Promtail, monitoring stack
make play-pangolin    # Pangolin stack + Newt agent (cross-inventory)
make play-authelia    # (stub)
make play-tailscale   # (stub)
make play-proxmox     # Proxmox host config

# Composite targets
make deploy-vm VM=<name>   # tofu apply (home+cloud) + VM playbook
make deploy-services       # infra + pangolin + monitoring playbooks
```

### Direct Ansible Operations

```bash
cd ansible

# Run a specific playbook
ansible-playbook playbooks/vms/infra.yml

# Run with specific tags
ansible-playbook playbooks/vms/database.yml --tags postgresql_install

# Run playbook for specific host
ansible-playbook playbooks/vms/infra.yml --limit infra

# List hosts in inventory
ansible-inventory --list

# Check connectivity
ansible all -m ping
```

**Important**: The default inventory in `ansible.cfg` is `ansible/inventories/local`. Use `make play-pangolin` (or `ansible-playbook -i inventories/ ...`) for the cross-inventory Pangolin playbook. Vault password is automatically loaded from `vault.auth`.

### Working with Ansible Vault

```bash
cd ansible

ansible-vault edit inventories/local/group_vars/all/vault.yml   # Edit
ansible-vault view inventories/local/group_vars/all/vault.yml   # View
ansible-vault rekey inventories/local/group_vars/all/vault.yml  # Change password
```

**Note**: The vault password file (`vault.auth`) is git-ignored and must exist for Ansible to decrypt vault files.

## Workflows

### Adding a New VM

Edit 3 files:

1. `config/network.json` — add the host IP (e.g., `"docs": "192.168.1.110"`)
2. `terraform/home/main.tf` — add VM definition to `local.servers`
3. `ansible/inventories/local/hosts.yml` — add hostname as `docs: {}` (no IP needed) + optional groups (`monitored_nodes`, `docker_monitored`)

Deploy:
```bash
make validate              # Check consistency
make deploy-vm VM=docs     # tofu apply (home+cloud) + ansible playbook
```

### Adding a Simple Service

A service where auto-generated Traefik/Pangolin routing is sufficient (no custom middleware, no special backends).

Edit 2 files:

1. `ansible/playbooks/vms/<host>.yml` — add tasks or roles to install the service
2. `config/services/<host>/<service>.yml` — create the service manifest with `mode: generated`

Example manifest:
```yaml
service_manifest:
  name: my-app
  display_name: My App
  host: tools
  service:
    port: 8080
    protocol: http
  exposure:
    local:
      enabled: true
      mode: generated
      template: simple-http
      subdomain: myapp
    public:
      enabled: true
      mode: generated
      subdomain: myapp
      protocol: http
  auth:
    sso: false
  deployment:
    owner: role
    role: my_app
```

Deploy:
```bash
make play-tools            # Install the service
make deploy-services       # Update routing (infra + pangolin + monitoring)
```

### Adding a Complex Service

A service that needs custom Traefik middleware, special backends (HTTPS with insecureSkipVerify), forwardAuth, etc.

Edit up to 4 files:

1. `ansible/playbooks/vms/<host>.yml` — install the service
2. `config/services/<host>/<service>.yml` — manifest with `mode: fragment` and `fragment: <name>`
3. `config/fragments/traefik/<fragment>.yml` — custom Traefik routing
4. `config/fragments/pangolin/<fragment>.yml` — custom Pangolin blueprint

Fragment file format (Traefik):
```yaml
traefik_fragment_services:
  - filename: my-service.yml
    content: |
      http:
        routers:
          my-service:
            rule: "Host(`myapp.{{ traefik_local_domain }}`)"
            entryPoints:
              - https
            service: my-service-svc
            tls:
              certResolver: {{ traefik_cert_resolver_name }}
            middlewares:
              - authelia
        services:
          my-service-svc:
            loadBalancer:
              servers:
                - url: "http://{{ hostvars['tools'].ansible_host }}:8080"
```

Fragment file format (Pangolin):
```yaml
pangolin_fragment_resources:
  unique-resource-id:
    name: My Service
    protocol: http
    full-domain: "myapp.{{ pangolin_base_domain }}"
    auth:
      sso-enabled: true
    targets:
      - site: "{{ pangolin_site_nice_id }}"
        hostname: "{{ hostvars['tools'].ansible_host }}"
        port: 8080
        method: http
```

Deploy:
```bash
make play-tools            # Install the service
make deploy-services       # Update routing
```

### Adding a New Ansible Role

1. Create role structure: `ansible/roles/<role_name>/{tasks,defaults,handlers,files,templates}/`
2. Define tasks in `tasks/main.yml`
3. Set defaults in `defaults/main.yml`
4. Reference role in appropriate playbook

### Database Setup Pattern

The database VM hosts multiple database engines. Each application database is configured in `ansible/playbooks/vms/database.yml`:
- PostgreSQL: Users and databases defined under `postgresql_users` and `postgresql_databases`
- InfluxDB: Databases defined under `influxdb_databases`
- Redis: Installed via geerlingguy.redis role with default configuration

Credentials are stored in vault as `vault.database.<service>_user_pw`.

## Important Files

### Configuration Authority
- `config/network.json`: Single source of truth for all host IPs
- `config/domains.yml`: Shared domain/email/network settings
- `config/services/`: Per-service manifests (exposure, auth, deployment)
- `config/fragments/traefik/`: Traefik routing fragments
- `config/fragments/pangolin/`: Pangolin blueprint fragments

### Ansible
- `ansible/ansible.cfg`: Ansible configuration (vault, plugins, inventory)
- `ansible/plugins/vars/network_json.py`: Vars plugin that sets `ansible_host` from `config/network.json`
- `ansible/inventories/local/hosts.yml`: Inventory defining host group membership (no IPs)
- `ansible/inventories/local/group_vars/all/vault.yml`: Encrypted secrets (git-tracked but encrypted)
- `ansible/requirements.yml`: External Ansible collections dependencies
- `.venv/`: Repo-local Python tooling environment created by `make bootstrap` (gitignored)

### Terraform
- `terraform/home/`: Proxmox LXC container definitions
- `terraform/cloud/`: Cloudflare DNS + AWS resource definitions
- `terraform/*/terraform.tfvars`: Variable values (git-ignored, contains secrets)

### Tooling
- `scripts/validate_sources.py`: Consistency checker across all sources of truth
- `Makefile`: All build, deploy, and validation targets

## Network and Access

- Local network: 192.168.1.0/24
- Gateway: 192.168.1.254
- SSH access: Configured via SSH public key (path specified in Terraform variables)
- All VMs use root SSH access with key authentication (ansible_user: root, key: ~/.ssh/homelab)
- Domain: local.batistela.tech (managed via Cloudflare DNS)
