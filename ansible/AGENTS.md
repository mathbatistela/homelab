# ANSIBLE LAYER

Configures services on Proxmox LXC containers and a remote VPS. Multi-inventory (local + cloud), encrypted vault, custom callback plugin.

## STRUCTURE

```
ansible/
├── ansible.cfg              # Vault auto-unlock, auto_tags plugin enabled
├── requirements.yml         # External collections (community.general, checkmk.general)
├── plugins/callbacks/       # auto_tags.py — auto-generates tag per role name
├── inventories/
│   ├── local/               # Proxmox hosts (proxmox group, monitored group)
│   │   ├── hosts.yml
│   │   ├── group_vars/all/  # main.yml (domain) + vault.yml (secrets)
│   │   └── host_vars/infra/ # Traefik + CheckMK host-specific vars
│   └── cloud/               # RackNerd VPS (racknerd group)
│       ├── hosts.yml
│       └── group_vars/all/
├── playbooks/
│   ├── vms/                 # Per-VM: database, infra, media, minecraft, tools, pangolin
│   ├── nodes/               # proxmox.yml (PVE node: storage, homeshare, templates)
│   └── monitoring.yml       # Standalone: monitoring_stack on infra
└── roles/                   # 12 custom + 3 external (vendored)
```

## WHERE TO LOOK

| Task | Location | Notes |
|------|----------|-------|
| Add new service to a VM | `playbooks/vms/<host>.yml` | Add play with role or tasks |
| Expose via Traefik | `playbooks/vms/infra.yml` | `include_role: traefik, tasks_from: configure_service` |
| Add Traefik template | `roles/traefik/templates/services/` | 3 templates: simple-http, with-middleware, tcp-service |
| Add PostgreSQL database | `playbooks/vms/database.yml` | Append to `postgresql_users` + `postgresql_databases` |
| Add InfluxDB database | `playbooks/vms/database.yml` | Append to `influxdb_databases` in influxdb role vars |
| Store new secret | `inventories/local/group_vars/all/vault.yml` | Pattern: `vault.<vm_group>.<secret_name>` |
| Add host-specific var | `inventories/local/host_vars/<host>/` | Create dir if new host |
| Add external collection | `requirements.yml` | Then `ansible-galaxy collection install -r requirements.yml` |
| Create custom role | `roles/<name>/` | Minimum: `tasks/main.yml` + `defaults/main.yml` |
| Configure PVE node | `playbooks/nodes/proxmox.yml` | Roles: pve_storage, pve_homeshare, pve_vmstorage, pve_templates |

## ROLES

### Custom Roles

| Role | VM | Pattern | Notes |
|------|----|---------|-------|
| `traefik` | infra | Binary install + systemd + template-based dynamic config | See `roles/traefik/README.md` |
| `arr_stack` | media | Docker Compose via `community.docker.docker_compose_v2` | Templates: docker-compose.yml.j2, env.j2 |
| `monitoring_stack` | infra | File sync only — `docker compose up` is **commented out** | Manual start required |
| `influxdb` | database | Split tasks: install.yml → setup.yml → databases.yml | Tagged per phase |
| `actual_budget` | tools | Docker container deployment | — |
| `minecraft_server` | minecraft | Direct install (no Docker) | Has handlers + templates |
| `samba_share` | media | Samba config with templates | Has handlers for restart |
| `checkmk_agent` | media | CheckMK agent deployment | Also uses `checkmk.general.agent` collection role |
| `pve_storage` | pve | Proxmox storage setup | Tasks only (no defaults) |
| `pve_homeshare` | pve | NFS/bind mount setup | — |
| `pve_vmstorage` | pve | VM disk storage | — |
| `pve_templates` | pve | LXC template downloads | — |

### External (Vendored in `roles/`, not `collections/`)

| Role | Source | Used In |
|------|--------|---------|
| `geerlingguy.docker` | Galaxy | media, tools, infra (pangolin) |
| `geerlingguy.postgresql` | Galaxy | database |
| `geerlingguy.redis` | Galaxy | database |

## CONVENTIONS

- **Playbook pattern**: Multiple plays per file, each targeting one role/concern. Tags on plays.
- **auto_tags plugin**: Every role automatically gets a tag matching its name — no manual tagging needed for `--tags <role_name>`
- **Docker services**: Use `geerlingguy.docker` role first, then `community.docker.docker_container` or `docker_compose_v2`
- **Traefik service config**: Prefer `template: simple-http` for basic services; use `content:` inline for complex configs
- **Vault access**: Always `vault.<group>.<key>`, never bare variable names for secrets
- **Host vars precedence**: `host_vars/<host>/main.yml` for non-secret overrides, vault for secrets
- **FQCN usage**: Mixed — newer playbooks use `ansible.builtin.*`, older ones use short module names

## ANTI-PATTERNS

- **Never** put secrets in `group_vars/all/main.yml` — use `vault.yml`
- **Never** create host_vars without checking if the host needs them — only `infra` has them currently
- **Never** add external roles to `requirements.yml` without also vendoring — galaxy install goes to `collections/` (gitignored)
- **Never** assume `monitoring_stack` auto-starts — compose up is intentionally commented out
- **Never** manually tag roles in playbooks — `auto_tags` plugin handles this automatically

## NOTES

- `pangolin.yml` is the only cross-host playbook: UFW on `racknerd_vm0` → Newt agent on `infra`
- `tools.yml` mixes role includes (`geerlingguy.docker`, `actual_budget`) with inline tasks (`portainer` container)
- `database.yml` uses `pre_tasks` block to add PostgreSQL APT repo before the `geerlingguy.postgresql` role runs
- Cloud inventory vars for `racknerd_vm0` reference variables that must be defined in cloud vault/group_vars
