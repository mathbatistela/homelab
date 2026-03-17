# PROJECT KNOWLEDGE BASE

**Generated:** 2026-03-17
**Commit:** ded5096
**Branch:** main

## OVERVIEW

Homelab IaC managing Proxmox LXC containers via Terraform (provisioning) + Ansible (configuration). Two separate Terraform modules (home/cloud), Ansible with custom roles, auto-tagging plugin, and encrypted vault secrets. Uses **OpenTofu** (`tofu`), not Hashicorp Terraform.

## STRUCTURE

```
homelab/
├── terraform/
│   ├── home/           # Proxmox LXC containers (Telmate/proxmox provider)
│   └── cloud/          # Cloudflare DNS + AWS (separate state)
├── ansible/            # Service configuration (see ansible/AGENTS.md)
│   ├── playbooks/vms/  # One playbook per VM
│   ├── roles/          # 12 custom + 3 external (geerlingguy.*)
│   ├── inventories/    # local/ (proxmox) + cloud/ (racknerd)
│   └── plugins/        # auto_tags callback
└── CLAUDE.md           # Detailed project docs + commands
```

## WHERE TO LOOK

| Task | Location | Notes |
|------|----------|-------|
| Add new LXC container | `terraform/home/main.tf` | Follow `proxmox_lxc.<name>_server` pattern |
| Add DNS for new VM | `terraform/cloud/vms_dns.tf` | Add to `local.hosts` list |
| Configure new service | `ansible/playbooks/vms/<host>.yml` | One playbook per target VM |
| Create Ansible role | `ansible/roles/<name>/` | Needs tasks/, defaults/ minimum |
| Expose service via Traefik | `ansible/playbooks/vms/infra.yml` | Use traefik `configure_service` task |
| Add database | `ansible/playbooks/vms/database.yml` | Add to `postgresql_users` + `postgresql_databases` |
| Store secrets | `ansible/inventories/local/group_vars/all/vault.yml` | Access as `vault.<vm>.<secret>` |
| Host-specific vars | `ansible/inventories/local/host_vars/<host>/` | Only `infra` has host_vars currently |

## CONVENTIONS

- **Terraform naming**: Resources = `proxmox_lxc.<purpose>_server`, outputs mirror resource names
- **Terraform split**: `home/` and `cloud/` are **independent modules** with separate state — run `tofu` from within each directory
- **IP allocation**: 192.168.1.{100+}, gateway .254. VMIDs match last octet (101→vmid 101)
- **Vault path**: `vault.<vm_group>.<secret_name>` (e.g., `vault.database.fresh_rss_user_pw`, `vault.infra.traefik_cloudflare_token`)
- **Playbook structure**: Multiple plays per file, each targeting a specific role/concern. Tags per play/role.
- **auto_tags plugin**: Automatically adds a tag matching each role name — no need to manually tag role includes
- **Domain**: `local.batistela.tech` (Cloudflare-managed, used for Traefik TLS certs via DNS challenge)

## ANTI-PATTERNS

- **Never** run `tofu` from `terraform/` root — modules are independent
- **Never** commit `*.tfvars`, `vault.auth`, `*.tfstate` — gitignored, contain secrets
- **Never** use `terraform` binary — project uses **OpenTofu** (`tofu`)
- **Never** hardcode IPs in roles — use inventory vars or vault. IPs are only hardcoded in Terraform `main.tf` and `vms_dns.tf`
- monitoring_stack `docker compose up` is **commented out** — manual step required after sync

## COMMANDS

```bash
# Terraform (run from module dir)
cd terraform/home && tofu plan && tofu apply
cd terraform/cloud && tofu plan && tofu apply

# Ansible (run from ansible/)
cd ansible
ansible-playbook playbooks/vms/<host>.yml              # Full VM config
ansible-playbook playbooks/vms/database.yml --tags postgresql_install
ansible-playbook playbooks/nodes/proxmox.yml            # PVE node setup
ansible-galaxy collection install -r requirements.yml   # Install deps
ansible-vault edit inventories/local/group_vars/all/vault.yml
```

## NETWORK MAP

| Host | IP | VMID | Purpose |
|------|----|------|---------|
| pve | 192.168.1.100 | — | Proxmox VE hypervisor |
| media | 192.168.1.101 | 101 | *arr stack, Samba |
| infra | 192.168.1.102 | 102 | Traefik, CheckMK, Newt agent |
| database | 192.168.1.103 | 103 | PostgreSQL, Redis, InfluxDB |
| minecraft | 192.168.1.105 | 105 | Minecraft server |
| tools | 192.168.1.107 | 107 | Portainer, Actual Budget |
| tailscale | 192.168.1.108 | 108 | VPN gateway |
| authelia | 192.168.1.109 | — | Auth (in inventory, no Terraform resource yet) |
| racknerd | 204.152.223.118 | — | Remote VPS (Pangolin tunnel) |

## NOTES

- `authelia` host is in Ansible inventory but has **no Terraform resource** — provisioned manually or missing
- `tailscale` host (108) is in inventory as part of old naming — CLAUDE.md references it but no dedicated playbook exists
- `pangolin.yml` playbook is cross-host: configures UFW on `racknerd_vm0` + deploys Newt agent on `infra`
- The `monitoring_stack` role syncs docker-compose files but does **not** start them (compose up is commented out)
- External roles (`geerlingguy.*`) are vendored in `ansible/roles/`, not in `collections/`
