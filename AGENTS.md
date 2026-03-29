# PROJECT KNOWLEDGE BASE

**Generated:** 2026-03-29
**Branch:** main

## OVERVIEW

Homelab IaC managing Proxmox LXC containers via OpenTofu (provisioning) + Ansible (configuration). Two separate Terraform modules (home/cloud), Ansible with custom roles, auto-tagging plugin, and encrypted vault secrets. Uses **OpenTofu** (`tofu`), not Hashicorp Terraform.

## STRUCTURE

```
homelab/
├── config/
│   ├── network.json    # Authoritative shared network config for Terraform modules
│   ├── domains.yml     # Authoritative shared domain/email/tunnel IP config
│   └── services/       # Pilot per-service manifests for simple generated routing/public exposure
├── terraform/          # Infrastructure provisioning (see terraform/AGENTS.md)
│   ├── home/           # Proxmox LXC containers (Telmate/proxmox provider)
│   │   ├── main.tf     # locals.servers map + proxmox_lxc.servers (for_each); IPs from config/network.json
│   │   ├── variables.tf # Provider creds + infra paths + lxc_ostemplate/bridge/interface vars
│   │   ├── outputs.tf   # Server vmid/hostname/ip map
│   │   └── providers.tf # Telmate/proxmox v3.0.2-rc07
│   └── cloud/          # Cloudflare DNS + AWS (separate state)
│       ├── dns.tf       # Pangolin wildcard + subdomain records
│       ├── vms_dns.tf   # Per-VM A records; IPs read from network.json
│       ├── variables.tf # Cloudflare/AWS creds + zone ID
│       ├── outputs.tf   # dns_records output
│       └── providers.tf # Cloudflare ~> 5.5.0, AWS ~> 5.0.0
├── ansible/            # Service configuration (see ansible/AGENTS.md)
│   ├── playbooks/vms/  # One playbook per VM (9 playbooks)
│   ├── roles/          # 16 custom + 3 external (geerlingguy.*)
│   ├── inventories/    # local/ (proxmox) + cloud/ (racknerd)
│   └── plugins/        # auto_tags callback
├── Makefile            # bootstrap, doctor, lint, syntax-check, play-*, plan-*, validate-*
└── CLAUDE.md           # Detailed project docs + commands
```

## WHERE TO LOOK

| Task | Location | Notes |
|------|----------|-------|
| Add new LXC container | `terraform/home/main.tf` + `config/network.json` | Add to `local.servers` map; add IP to `config/network.json` |
| Add DNS for new VM | `terraform/cloud/vms_dns.tf` + `config/network.json` | IPs come from `config/network.json`; update `local_hosts` there |
| Configure new service | `ansible/playbooks/vms/<host>.yml` | One playbook per target VM |
| Create Ansible role | `ansible/roles/<name>/` | Needs tasks/, defaults/ minimum |
| Expose service via Traefik | `ansible/inventories/local/host_vars/infra/traefik_*_services.yml` | Add to the relevant concern file; `traefik_services.yml` composes them |
| Expose service via Pangolin | `ansible/inventories/cloud/group_vars/all/pangolin_blueprint_*.yml` | Add to the relevant concern file; `pangolin_blueprint.yml` composes them |
| Add database | `ansible/inventories/local/host_vars/database/postgresql_databases.yml` | Add to `postgresql_users` + `postgresql_databases` |
| Store secrets | `ansible/inventories/local/group_vars/all/vault.yml` | Access as `vault.<vm>.<secret>` |
| Host-specific vars | `ansible/inventories/local/host_vars/<host>/` | infra, database, pve have host_vars |
| Change network config | `config/network.json` | Gateway, subnet, cidr, all host IPs live here |
| Change shared domain/email config | `config/domains.yml` | base_domain, local_domain, admin_email, tunnel IPs |
| Add simple service manifest | `config/services/<group>/<service>.yml` | Pilot manifests currently generate simple Traefik/Pangolin entries |

## CONVENTIONS

- **Terraform naming**: `local.servers` map → `proxmox_lxc.servers` for_each; IPs sourced from `local.network.local_hosts.<name>` via `config/network.json`
- **Terraform split**: `home/` and `cloud/` are **independent modules** with separate state. Run `tofu` from within each directory
- **config/network.json**: Both TF modules read it via `jsondecode(file("${path.module}/../../config/network.json"))`. Contains `local_hosts` (hostname→IP map), `remote_hosts`, `gateway`, `cidr`, `subnet`
- **IP allocation**: 192.168.1.{100+}, gateway .254. VMIDs match last octet (101→vmid 101)
- **Vault path**: `vault.<vm_group>.<secret_name>` (e.g., `vault.database.fresh_rss_user_pw`, `vault.infra.traefik_cloudflare_token`)
- **Playbook structure**: Multiple plays per file, each targeting a specific role/concern. Tags per play/role.
- **auto_tags plugin**: Automatically adds a tag matching each role name. No need to manually tag role includes.
- **Domain (local)**: `local.batistela.tech` — derived from `base_domain` + `local_domain` in `config/domains.yml`
- **Domain (public)**: `batistela.tech` — defined as `base_domain` in `config/domains.yml`
- **admin_email**: `matheus@batistela.tech` — defined as `admin_email: "matheus@{{ base_domain }}"` in `config/domains.yml`; used by traefik and pangolin roles
- **Service manifest pilot**: `config/services/` holds per-service metadata for simple generated routes/resources. Current pilot services: `actual-budget`, `jellyfin`, `n8n`, `grafana`, `prometheus`, `alertmanager`, `ha`
- **Service manifest ports**: For manifest-driven services, the service manifest owns the port/protocol. No separate shared port registry exists yet.

## ANTI-PATTERNS

- **Never** run `tofu` from `terraform/` root — modules are independent
- **Never** commit `*.tfvars`, `vault.auth`, `*.tfstate` — gitignored, contain secrets
- **Never** use `terraform` binary — project uses **OpenTofu** (`tofu`)
- **Never** hardcode IPs in roles — use inventory vars or hostvars references
- **Never** hardcode IPs in Terraform — read from `config/network.json`
- monitoring_stack `docker compose up` is **commented out** — manual step required after sync

## COMMANDS

```bash
# Terraform (run from module dir)
cd terraform/home && tofu plan && tofu apply
cd terraform/cloud && tofu plan && tofu apply

# Ansible (run from ansible/)
cd ansible
. ../.venv/bin/activate
ansible-playbook playbooks/vms/<host>.yml               # Full VM config
ansible-playbook playbooks/vms/database.yml --tags postgresql_install
ansible-playbook playbooks/nodes/proxmox.yml            # PVE node setup
ansible-vault edit inventories/local/group_vars/all/vault.yml

# Makefile shortcuts (from repo root)
make bootstrap                   # Create .venv, install Python deps and collections
make doctor                      # Verify local toolchain and collections
make play-infra                  # ansible-playbook playbooks/vms/infra.yml
make play-database               # ansible-playbook playbooks/vms/database.yml
make lint                        # ansible-lint --offline playbooks/ (lint debt still exists)
make syntax-check                # syntax-check all playbooks
make plan-home                   # tofu plan (home module)
make plan-cloud                  # tofu plan (cloud module)
```

## NETWORK MAP

| Host | IP | VMID | Purpose |
|------|----|------|---------|
| pve | 192.168.1.100 | — | Proxmox VE hypervisor |
| media | 192.168.1.101 | 101 | *arr stack, Samba, Kavita, ebookdl |
| infra | 192.168.1.102 | 102 | Traefik, monitoring stack, Newt agent |
| database | 192.168.1.103 | 103 | PostgreSQL 17, InfluxDB 3, Redis |
| minecraft | 192.168.1.105 | 105 | Minecraft server (bare metal, no Docker) |
| n8n | 192.168.1.106 | — | n8n automation (no Terraform resource) |
| tools | 192.168.1.107 | 107 | Portainer, Actual Budget, adhd-board |
| tailscale | 192.168.1.108 | 108 | VPN gateway |
| authelia | 192.168.1.109 | — | Auth (no Terraform resource) |
| racknerd | 204.152.223.118 | — | Remote VPS (Pangolin tunnel) |

**Unmanaged hosts** (in Ansible `unmanaged` group, no playbook, IPs accessible via `hostvars`):

| Host | IP | Referenced Via |
|------|----|----------------|
| ha | 192.168.1.75 | `hostvars['ha'].ansible_host` |
| n8n | 192.168.1.106 | `hostvars['n8n'].ansible_host` |

**Tunnel/Tailscale IPs** (defined in `config/domains.yml` and mirrored in inventory `network.yml` files when needed):

| Variable | IP | Used In |
|----------|----|---------|
| `tailscale_ha_ip` | 100.75.65.121 | traefik_services.yml |

## KNOWN ISSUES & IMPROVEMENT OPPORTUNITIES

### RESOLVED: IP Address Duplication

Previously IPs were duplicated across 4 locations. Now resolved:
- **`config/network.json`** — single source of truth for all host IPs, gateway, subnet, cidr for Terraform
- Both TF modules (`home/main.tf`, `cloud/vms_dns.tf`) read from `config/network.json` via `jsondecode`
- **`ansible/inventories/local/hosts.yml`** — Ansible inventory (separate concern; should stay aligned with `config/network.json`)
- Pangolin blueprint now uses `hostvars` references for managed hosts and unmanaged hosts

Changing an IP now requires editing `config/network.json` (for Terraform) and `hosts.yml` (for Ansible) — 2 files instead of 4.

### RESOLVED: Hardcoded Infrastructure Values in Terraform

`terraform/home/variables.tf` now exposes:
- `lxc_ostemplate` — OS template path (with default)
- `lxc_network_bridge` — network bridge name (default: `vmbr0`)
- `lxc_network_interface` — interface name (default: `eth0`)

Gateway reads from `local.network.gateway` in `config/network.json`. Startup order remains identical for all containers (no per-container priority yet).

### RESOLVED: Inconsistent Service Discovery

All service references now use a consistent pattern:
- **Managed hosts**: `http://{{ hostvars['<host>'].ansible_host }}:<port>` — used in both Traefik and Pangolin concern files
- **Unmanaged hosts** (HA, n8n): added to Ansible `unmanaged` group in `hosts.yml`, referenced via `hostvars['ha'].ansible_host` and `hostvars['n8n'].ansible_host`
- **Tunnel IPs**: `tailscale_ha_ip` defined in `config/domains.yml` and mirrored for inventory use

### RESOLVED: Domain Name Fragmentation

Domain variables now defined once in `config/domains.yml` and mirrored into inventory `network.yml` files:
```
base_domain: batistela.tech
local_domain: "local.{{ base_domain }}"
admin_email: "matheus@{{ base_domain }}"
```
`host_vars/infra/main.yml` sets `traefik_local_domain: "{{ local_domain }}"`. Role defaults derive from `local_domain` and `admin_email`. `actual_budget` template uses `{{ base_domain }}` instead of hardcoded string.

### RESOLVED: Inline Variables in database.yml

PostgreSQL users, databases, and APT repo config moved to `host_vars/database/postgresql_databases.yml`. Playbook now references `postgresql_repo.key_url` etc. from host_vars. HBA entry in `postgresql.yml` uses `{{ network_subnet }}` instead of hardcoded `192.168.1.0/24`.

### RESOLVED: Missing Terraform Outputs

`terraform/cloud/outputs.tf` now exports `dns_records`.

### MEDIUM: No Centralized Port Registry

Service ports scattered across:
- Role defaults (node_exporter: 9100, cadvisor: 9080, promtail→loki: 3100, influxdb: 8181)
- `traefik_*_services.yml` (arr stack: 9696/8989/7878/8787/6767/7575/8096/8080)
- `pangolin_blueprint_*.yml` (duplicates many of the same ports)
- `portainer/defaults/main.yml` (8000, 9443)

### RESOLVED: Large Mixed-Concern Files

Routing/public exposure config is now split by concern:
- **Traefik**: `traefik_simple_services.yml`, `traefik_tcp_services.yml`, `traefik_media_services.yml`, `traefik_auth_services.yml`, `traefik_admin_services.yml`
- **Pangolin**: `pangolin_blueprint_media.yml`, `pangolin_blueprint_home.yml`, `pangolin_blueprint_tools.yml`, `pangolin_blueprint_auth.yml`

The original `traefik_services.yml` and `pangolin_blueprint.yml` remain as composition entrypoints to preserve consumer behavior.

### PILOT: Service Manifest Generation

The repo now has an initial `config/services/` layer for simple service metadata:
- `config/services/tools/actual-budget.yml`
- `config/services/media/jellyfin.yml`
- `config/services/home/n8n.yml`
- `config/services/infra/grafana.yml`
- `config/services/infra/prometheus.yml`
- `config/services/infra/alertmanager.yml`
- `config/services/home/ha.yml`

`infra.yml` loads these manifests at runtime and generates simple Traefik entries for services with `exposure.local.mode: generated`.
`pangolin.yml` loads these manifests at runtime and generates simple Pangolin public resources for services with `exposure.public.mode: generated`.

Complex services still stay in manual fragments:
- Traefik: arr-stack, auth, admin, TCP special cases
- Pangolin: services with custom rules/healthchecks beyond the simple generated shape

Schema v1 rule of thumb:
- `mode: generated` → standard resource generated from manifest
- `mode: custom` + `fragment: <name>` → handled by manual fragment files

## NOTES

- `authelia`, `n8n`, and Home Assistant have **no Terraform resource** — provisioned manually
- `authelia` and `tailscale` have placeholder playbooks — deployed but not yet fully Ansible-managed
- `pangolin.yml` playbook is cross-host: configures UFW on `racknerd_vm0` + deploys Newt agent on `infra`
- The `monitoring_stack` role syncs docker-compose files but does **not** start them (compose up is commented out)
- External roles (`geerlingguy.*`) are vendored in `ansible/roles/`, not in `collections/`
- Cloud inventory uses variables for host connection (`racknerd_vm0_ip`, etc.) — defined in cloud vault
- `tools.yml` is the only playbook that puts multiple roles in a single play (docker + actual_budget + portainer)
