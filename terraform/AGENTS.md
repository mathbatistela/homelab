# TERRAFORM LAYER

OpenTofu infrastructure provisioning for Proxmox LXC containers and Cloudflare DNS. Two independent modules with separate state.

## STRUCTURE

```
terraform/
├── home/               # Proxmox LXC containers (local infrastructure)
│   ├── main.tf         # locals.servers map + proxmox_lxc.servers resource
│   ├── variables.tf    # PVE creds, paths, LXC template/network vars
│   ├── outputs.tf      # Server vmid/hostname/ip map
│   ├── providers.tf    # Telmate/proxmox v3.0.2-rc07
│   ├── terraform.tfvars # Secrets (gitignored)
│   └── .terraform/     # Provider plugins
└── cloud/              # Cloudflare DNS + AWS (remote resources)
    ├── dns.tf          # Pangolin wildcard + subdomain records
    ├── vms_dns.tf      # Per-VM A records from network.json
    ├── variables.tf    # Cloudflare/AWS creds + zone ID
    ├── outputs.tf      # dns_records output
    ├── providers.tf    # Cloudflare ~> 5.5.0, AWS ~> 5.0.0
    └── terraform.tfvars # Secrets (gitignored)
```

## WHERE TO LOOK

| Task | Location | Notes |
|------|----------|-------|
| Add new LXC container | `home/main.tf` + `../config/network.json` | Add to `local.servers` map; add IP to network.json |
| Change VM resources | `home/main.tf` | Edit cores/memory/disk in `local.servers.<name>` |
| Add mountpoint | `home/main.tf` | Add to `mountpoints` list for the VM |
| Add DNS record | `cloud/dns.tf` | Add to existing records or create new resource |
| Add VM DNS entry | `cloud/vms_dns.tf` | IPs auto-read from network.json |
| Change network config | `home/variables.tf` | `lxc_network_bridge`, `lxc_network_interface` |
| Change OS template | `home/variables.tf` | `lxc_ostemplate` default |

## CONVENTIONS

- **Tool**: Always use `tofu` (OpenTofu), never `terraform` binary
- **State separation**: `home/` and `cloud/` are independent — separate state files, separate applies
- **Config source**: Both modules read `../config/network.json` via `jsondecode()`
- **Server definition**: `local.servers` map uses for_each → `proxmox_lxc.servers`
- **IP allocation**: VMIDs match last IP octet (101→vmid 101, .102→102)
- **Network**: Gateway from `local.network.gateway`, CIDR from `local.network.cidr`
- **Lifecycle**: Ignores ostemplate, password, ssh_keys, rootfs storage to prevent recreate
- **Startup**: All containers use `order=1,up=30,down=30` (no per-container priority yet)

## ANTI-PATTERNS

- **Never** run `tofu` from `terraform/` root — modules are independent, cd into `home/` or `cloud/`
- **Never** commit `*.tfvars` — contains secrets, gitignored
- **Never** commit `*.tfstate*` — contains state, gitignored
- **Never** hardcode IPs in .tf files — read from `config/network.json`
- **Never** modify `.terraform.lock.hcl` manually — use `tofu providers lock`

## COMMANDS

```bash
# Always run from within the module directory
cd terraform/home
cd terraform/cloud

# Plan/apply (must be in module dir)
tofu plan
tofu apply

# Validate
tofu validate

# Format
tofu fmt

# Makefile shortcuts (from repo root)
make plan-home        # cd terraform/home && tofu plan
make plan-cloud       # cd terraform/cloud && tofu plan
make apply-home       # cd terraform/home && tofu apply
make apply-cloud      # cd terraform/cloud && tofu apply
make validate-home    # tofu validate (home module)
make validate-cloud   # tofu validate (cloud module)
```

## NOTES

- `n8n`, `authelia`, and `ha` have **no Terraform resources** — provisioned manually or externally
- `home/` uses Telmate/proxmox provider for Proxmox VE API
- `cloud/` uses Cloudflare provider for DNS management
- Both modules use shared `config/network.json` for IP allocation consistency
- `minecraft-be` is defined in `home/main.tf` but may not be deployed

---
**Last Updated**: 2026-03-29
