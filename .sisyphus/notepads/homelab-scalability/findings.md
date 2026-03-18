
## Task: Replace Hardcoded IPs in infra.yml

**Date:** 2026-03-17
**Status:** ✅ COMPLETED

### Changes Made
- **Line 22**: `http://192.168.1.107:5006` → `http://{{ hostvars['tools'].ansible_host }}:5006`
- **Line 54**: `http://192.168.1.109:9091/api/authz/forward-auth` → `http://{{ hostvars['authelia'].ansible_host }}:9091/api/authz/forward-auth`
- **Line 67**: `http://192.168.1.109:9091` → `http://{{ hostvars['authelia'].ansible_host }}:9091`
- **Line 99**: `https://192.168.1.107:9443` → `https://{{ hostvars['tools'].ansible_host }}:9443`

### Verification
✅ Syntax check passed: `ansible-playbook playbooks/vms/infra.yml --syntax-check`
✅ No hardcoded `192.168.1.*` IPs remain in playbooks/ or roles/ (excluding inventories/)
✅ Both `tools` and `authelia` hosts are defined in `inventories/local/hosts.yml`
✅ All 4 IP references successfully replaced with hostvars

### Impact
- infra.yml is now resilient to IP changes
- If tools or authelia hosts are re-IPed in inventory, Traefik config will automatically use new IPs
- No manual updates needed to playbook when IPs change

## Task: Actual Budget Role Defaults Extraction

**Date:** 2026-03-17

### Completed
- ✅ Created `ansible/roles/actual_budget/defaults/main.yml` with 2 path variables:
  - `actual_budget_data_dir: /mnt/homeshare/docker/actual-budget`
  - `actual_budget_compose_dir: /root/docker-compose-apps/actual-budget`
- ✅ Updated `ansible/roles/actual_budget/tasks/main.yml` — replaced all 4 hardcoded paths:
  - Line 4: `/mnt/homeshare/docker/actual-budget` → `{{ actual_budget_data_dir }}`
  - Line 12: `/root/docker-compose-apps/actual-budget` → `{{ actual_budget_compose_dir }}`
  - Line 21: `/root/docker-compose-apps/actual-budget/docker-compose.yml` → `{{ actual_budget_compose_dir }}/docker-compose.yml`
  - Line 28: `/root/docker-compose-apps/actual-budget` → `{{ actual_budget_compose_dir }}`
- ✅ Syntax check passed: `ansible-playbook playbooks/vms/tools.yml --syntax-check`

### Pattern Applied
Follows Ansible best practice: hardcoded paths → defaults/main.yml variables. Enables easy customization per environment without modifying tasks.

### Notes
- Default values match current runtime paths exactly
- No other variables modified
- Docker-compose template unchanged
- tools.yml playbook now includes: geerlingguy.docker, actual_budget, portainer roles

## Task: Harden Terraform Provider Version Constraints

**Date:** 2026-03-17
**Status:** ✅ COMPLETED

### Telmate/proxmox Provider Status
- Checked registry: `https://registry.terraform.io/v1/providers/Telmate/proxmox/versions`
- **No stable release exists** — all 3.x versions are RC (release candidates)
- Latest available: `3.0.2-rc07` (upgraded from `3.0.2-rc01`)
- Full version history in 3.x: rc01 through rc07, plus 3.0.1-rc1 through rc10
- Last stable series: 2.9.x (latest: `2.9.14`) — but incompatible with current config

### Changes Made
- `terraform/home/providers.tf`: Added `required_version = ">= 1.6.0"`, upgraded proxmox to `3.0.2-rc07` with RC comment
- `terraform/cloud/providers.tf`: Added `required_version = ">= 1.6.0"`, normalized AWS `~> 5.0` → `~> 5.0.0`

### Validation
- `tofu validate` passes in both `terraform/home/` and `terraform/cloud/`
