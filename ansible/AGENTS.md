# ANSIBLE LAYER

Configures services on Proxmox LXC containers and a remote VPS. Multi-inventory (local + cloud), encrypted vault, custom callback plugin.

## STRUCTURE

```
ansible/
├── ansible.cfg              # Vault auto-unlock, auto_tags plugin enabled
├── requirements.yml         # External collections (community.general, community.docker, community.postgresql, ansible.posix)
├── plugins/callbacks/       # auto_tags.py — auto-generates tag per role name
├── inventories/
│   ├── local/               # Proxmox hosts (proxmox group, monitored_nodes, docker_monitored)
│   │   ├── hosts.yml        # 8 managed hosts + unmanaged group (ha, n8n)
│   │   ├── group_vars/all/  # network.yml mirror + vault.yml (secrets)
│   │   └── host_vars/       # infra/ (traefik fragments + composition), database/ (postgresql + postgresql_databases), pve/ (storage)
│   └── cloud/               # RackNerd VPS (racknerd group)
│       ├── hosts.yml         # 1 host: racknerd_vm0 (IP from vault vars)
│       └── group_vars/all/   # network.yml mirror + pangolin blueprint fragments/composition + vault.yml
├── playbooks/
│   ├── vms/                 # Per-VM: database, infra, media, minecraft, tools, pangolin, authelia, tailscale, monitoring
│   ├── nodes/               # proxmox.yml (PVE node: storage, homeshare, templates)
│   └── monitoring.yml       # Standalone: monitoring_stack on infra
└── roles/                   # 16 custom + 3 external (vendored)
```

## WHERE TO LOOK

| Task | Location | Notes |
|------|----------|-------|
| Add new service to a VM | `playbooks/vms/<host>.yml` | Add play with role or tasks |
| Expose via Traefik | `inventories/local/host_vars/infra/traefik_*_services.yml` | Add to the relevant concern file; `traefik_services.yml` composes them |
| Add Traefik template | `roles/traefik/templates/services/` | 3 templates: simple-http, with-middleware, tcp-service |
| Add PostgreSQL database | `inventories/local/host_vars/database/postgresql_databases.yml` | Append to `postgresql_users` + `postgresql_databases` |
| Add InfluxDB database | `playbooks/vms/database.yml` | Append to `influxdb_databases` in influxdb role vars |
| Store new secret | `inventories/local/group_vars/all/vault.yml` | Pattern: `vault.<vm_group>.<secret_name>` |
| Add host-specific var | `inventories/local/host_vars/<host>/` | Create dir if new host; infra, database, pve have host_vars |
| Add external collection | `requirements.yml` | Then `make bootstrap` to install into `ansible/collections/` |
| Create custom role | `roles/<name>/` | Minimum: `tasks/main.yml` + `defaults/main.yml` |
| Configure PVE node | `playbooks/nodes/proxmox.yml` | Roles: pve_storage, pve_homeshare, pve_vmstorage, pve_templates |
| Expose via Pangolin (public) | `inventories/cloud/group_vars/all/pangolin_blueprint_*.yml` | Add to the relevant concern file; `pangolin_blueprint.yml` composes them |
| Change domain/email vars | `config/domains.yml` | authoritative shared domain/email/tunnel IP values |
| Add simple service manifest | `../config/services/<group>/<service>.yml` | Pilot manifests are loaded at runtime by `infra.yml` and `pangolin.yml` |

## ROLES

### Custom Roles

| Role | VM | Pattern | Notes |
|------|----|---------|-------|
| `traefik` | infra | Binary install + systemd + template-based dynamic config | See `roles/traefik/README.md` |
| `arr_stack` | media | Docker Compose via `community.docker.docker_compose_v2` | Templates: docker-compose.yml.j2, env.j2 |
| `monitoring_stack` | infra | File sync only — `docker compose up` is **commented out** | Manual start required |
| `influxdb` | database | Split tasks: install.yml → setup.yml → databases.yml | Tagged per phase |
| `actual_budget` | tools | Docker container deployment | Has docker-compose.yml.j2 template; uses `{{ base_domain }}` |
| `portainer` | tools | Docker container via `community.docker.docker_container` | Ports 8000, 9443 |
| `minecraft_server` | minecraft | Direct install (no Docker), Temurin JDK | Has handlers + templates |
| `samba_share` | media | Samba config with templates | Has handlers for restart |
| `node_exporter` | monitored_nodes | Binary install + systemd | Port 9100 |
| `cadvisor` | docker_monitored | Docker container | Port 9080 |
| `promtail` | monitored_nodes | Docker container → pushes to Loki on infra | Port 3100 (Loki target) |
| `pangolin` | racknerd_vm0 | Docker Compose stack (Pangolin + Gerbil + CrowdSec) | Blueprint-driven config; uses `admin_email` |
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

## INVENTORY GROUPS

```
all
├── proxmox              # All LXC containers (root SSH, key auth)
│   ├── pve, media, infra, database, minecraft, tools, tailscale, authelia
├── monitored_nodes      # Hosts with node_exporter + promtail
│   ├── pve, media, database, minecraft, tools, tailscale
├── docker_monitored     # Hosts with cadvisor
│   ├── media, tools
├── unmanaged            # No playbook; IPs accessible via hostvars
│   ├── ha (192.168.1.75), n8n (192.168.1.106)
└── racknerd (cloud)     # Remote VPS
    └── racknerd_vm0
```

## VARIABLE HIERARCHY (Current State)

```
config/domains.yml             → base_domain, local_domain, admin_email
                                  network_gateway, network_subnet, network_cidr
                                  tailscale_ha_ip
group_vars/all/network.yml     → mirror of config/domains.yml for inventory compatibility
group_vars/all/vault.yml       → vault.{database,infra,tools,all}.* secrets

host_vars/infra/main.yml       → traefik_local_domain: "{{ local_domain }}", traefik_cert_resolver_name
host_vars/infra/traefik_*_services.yml → concern-specific Traefik service fragments
host_vars/infra/traefik_services.yml → composed traefik_services list
host_vars/database/postgresql.yml → PostgreSQL version, paths, HBA (uses {{ network_subnet }}), tuning params
host_vars/database/postgresql_databases.yml → postgresql_users, postgresql_databases, postgresql_repo config
host_vars/pve/main.yml         → PVE node config, storage paths, disk partitions

role defaults/main.yml         → Per-role configuration (versions, paths, ports); traefik/pangolin use admin_email
config/services/**/*.yml       → pilot per-service manifests for simple generated Traefik/Pangolin entries
```

## CONVENTIONS

- **Playbook pattern**: Multiple plays per file, each targeting one role/concern. Tags on plays.
- **auto_tags plugin**: Every role automatically gets a tag matching its name — no manual tagging needed for `--tags <role_name>`
- **Docker services**: Use `geerlingguy.docker` role first, then `community.docker.docker_container` or `docker_compose_v2`
- **Traefik service config**: Prefer `template: simple-http` for basic services; use `content:` inline for complex configs
- **Vault access**: Always `vault.<group>.<key>`, never bare variable names for secrets
- **Host vars precedence**: `host_vars/<host>/main.yml` for non-secret overrides, vault for secrets
- **FQCN usage**: Mixed — newer playbooks use `ansible.builtin.*`, older ones use short module names
- **Service discovery**: Use `hostvars['<host>'].ansible_host` for all hosts (managed and unmanaged). Tunnel-only endpoints use named variables like `tailscale_ha_ip`
- **Domain variables**: Always derive from `base_domain` and `local_domain` in `config/domains.yml` — inventory `network.yml` files mirror that data for compatibility
- **Email variable**: Use `admin_email` from `config/domains.yml` — never hardcode `matheus@batistela.tech`
- **Tooling workflow**: Use `make bootstrap` to create `.venv` and install collections, `make doctor` to verify setup, and Make targets for lint/syntax
- **Service manifest pilot**: Simple services can live in `config/services/`; runtime generation handles standard Traefik/Pangolin entries while complex routing stays in manual fragments
- **Schema v1**: `mode: generated` means runtime generation; `mode: custom` with `fragment` means the manifest records intent while manual fragment files own the final routing shape
- **Manifest-owned ports**: For manifest-driven services, port/protocol live in the manifest itself rather than a separate registry

## ANTI-PATTERNS

- **Never** put secrets in `config/domains.yml` or `group_vars/all/network.yml` — use `vault.yml`
- **Never** create host_vars without checking if the host needs them — only `infra`, `database`, `pve` have them
- **Never** add external roles to `requirements.yml` without also vendoring — galaxy install goes to `collections/` (gitignored)
- **Never** assume `monitoring_stack` auto-starts — compose up is intentionally commented out
- **Never** manually tag roles in playbooks — `auto_tags` plugin handles this automatically
- **Never** hardcode IPs in roles — use `hostvars['<host>'].ansible_host` or variables
- **Never** hardcode domain strings in templates or role defaults — use `base_domain`, `local_domain`, `admin_email`
- **Never** rely on globally installed ansible-lint/ansible-playbook — use the repo `.venv` through Make targets

## KNOWN ISSUES & IMPROVEMENT OPPORTUNITIES

### RESOLVED: Hardcoded IPs in traefik_services.yml & pangolin_blueprint.yml

All service references now use consistent patterns:
- `traefik_services.yml`: HA, n8n, and test service now use `hostvars['ha'].ansible_host`, `hostvars['n8n'].ansible_host`, and `tailscale_ha_ip`
- `pangolin_blueprint.yml`: all 12+ hardcoded IPs replaced with `hostvars['<host>'].ansible_host` for managed and unmanaged hosts
- Unmanaged hosts (HA, n8n) added to `unmanaged` inventory group so their IPs are accessible via `hostvars`

### RESOLVED: Domain Variable Chain is Redundant

Domain variables now defined once in `config/domains.yml` and mirrored into inventory `network.yml` files:
```
base_domain: batistela.tech
local_domain: "local.{{ base_domain }}"
admin_email: "matheus@{{ base_domain }}"
```
`host_vars/infra/main.yml` sets `traefik_local_domain: "{{ local_domain }}"`. Role defaults derive from `local_domain` and `admin_email`. `actual_budget` template uses `{{ base_domain }}`.

### RESOLVED: database.yml Used Inline Variables

PostgreSQL users, databases, and APT repo config moved to `host_vars/database/postgresql_databases.yml`. Playbook now references `postgresql_repo.key_url` etc. from host_vars. HBA entry in `postgresql.yml` uses `{{ network_subnet }}` instead of hardcoded `192.168.1.0/24`.

### RESOLVED: Email Addresses Hardcoded in Role Defaults

`matheus@batistela.tech` in `roles/traefik/defaults/main.yml` and `roles/pangolin/defaults/main.yml` now use `admin_email` variable sourced from `config/domains.yml`.

### RESOLVED: Routing Config Split by Concern

Traefik and Pangolin routing config is now split into concern-specific files and composed at the original variable entrypoints:

- **Traefik fragments**
  - `traefik_simple_services.yml`
  - `traefik_tcp_services.yml`
  - `traefik_media_services.yml`
  - `traefik_auth_services.yml`
  - `traefik_admin_services.yml`
- **Pangolin fragments**
  - `pangolin_blueprint_media.yml`
  - `pangolin_blueprint_home.yml`
  - `pangolin_blueprint_tools.yml`
  - `pangolin_blueprint_auth.yml`

This keeps consumer behavior unchanged while making routing config easier to navigate and extend.

### PILOT: Service Manifest Generation for Simple Services

`infra.yml` and `pangolin.yml` now load `config/services/**/*.yml` at runtime and generate standard entries for a small pilot set of simple services.

Current pilot manifests:
- `config/services/tools/actual-budget.yml`
- `config/services/media/jellyfin.yml`
- `config/services/home/n8n.yml`
- `config/services/infra/grafana.yml`
- `config/services/infra/prometheus.yml`
- `config/services/infra/alertmanager.yml`
- `config/services/home/ha.yml`

Rule of thumb:
- **Simple generated services** → manifest-driven
- **Complex/custom routing** → keep in manual fragment files

### MEDIUM: No Centralized Port Registry

Ports defined in multiple locations with no single reference:

| Port | Service | Defined In |
|------|---------|-----------|
| 9696 | Prowlarr | traefik_services.yml, pangolin_blueprint.yml |
| 8989 | Sonarr | traefik_services.yml |
| 7878 | Radarr | traefik_services.yml |
| 8787 | Readarr | traefik_services.yml |
| 6767 | Bazarr | traefik_services.yml |
| 7575 | Homarr | traefik_services.yml |
| 8096 | Jellyfin | traefik_services.yml, pangolin_blueprint.yml |
| 8080 | qBittorrent | traefik_services.yml |
| 9100 | node_exporter | roles/node_exporter/defaults |
| 9080 | cadvisor | roles/cadvisor/defaults |
| 3100 | Loki (promtail target) | roles/promtail/defaults |
| 8181 | InfluxDB | roles/traefik/defaults |
| 8000, 9443 | Portainer | roles/portainer/defaults, traefik_services.yml, pangolin_blueprint.yml |
| 5006 | Actual Budget | traefik_services.yml, pangolin_blueprint.yml |
| 9091 | Authelia | traefik_services.yml, pangolin_blueprint.yml |
| 25565 | Minecraft | traefik_services.yml, pangolin_blueprint.yml |

### LOW: tools.yml Mixes Multiple Roles in One Play

`tools.yml` is the only playbook that combines `geerlingguy.docker`, `actual_budget`, and `portainer` in a single play rather than separate plays per role. Other playbooks use separate plays per role with individual tags.

## NOTES

- `pangolin.yml` is the only cross-host playbook: UFW on `racknerd_vm0` → Newt agent on `infra`
- `database.yml` uses `pre_tasks` block to add PostgreSQL APT repo before the `geerlingguy.postgresql` role runs
- Cloud inventory vars for `racknerd_vm0` reference variables that must be defined in cloud vault/group_vars
- `authelia.yml` and `tailscale.yml` are placeholder playbooks — hosts are deployed but not yet Ansible-managed
- `infra.yml` uses data-driven Traefik config: concern files compose into `host_vars/infra/traefik_services.yml`, then looped in a single play
- `monitoring.yml` is a standalone playbook (not per-VM pattern) — deploys monitoring_stack on infra only
