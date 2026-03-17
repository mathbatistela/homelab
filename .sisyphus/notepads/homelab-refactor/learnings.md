# Learnings

## Project Conventions
- OpenTofu (`tofu`), NOT `terraform` binary
- Ansible run from `ansible/` subdirectory
- Vault: `vault.<vm_group>.<secret_name>` pattern
- All local hosts: `ansible_user: root` (so adding become: true is always a no-op)
- Custom roles use `ansible.builtin.*` FQCN (except geerlingguy.* which are vendored external)
- `synchronize` module is `ansible.posix.synchronize`, NOT `ansible.builtin`
- `apt_key`, `apt_repository` are `ansible.builtin.*`
- `proxmox.yml` intentionally sets `gather_facts: false` — do NOT change
- Monitoring stack: `docker compose up` is intentionally commented out — do NOT uncomment
- Terraform state files are local (gitignored): `terraform/home/terraform.tfstate`
- Two independent Terraform modules: `terraform/home/` and `terraform/cloud/` — NEVER run from `terraform/` root

- `ansible/playbooks/vms/database.yml`: keep PostgreSQL user passwords aligned with `vault.database.<user>_pw`, and add new app databases to `postgresql_databases` alongside the matching user.

## FQCN Standardization (2026-03-17)

Successfully standardized 3 files to use fully-qualified collection names (FQCN):

### Files Modified
1. `ansible/roles/samba_share/tasks/main.yml` - 4 modules updated
   - apt → ansible.builtin.apt
   - file → ansible.builtin.file (2x)
   - template → ansible.builtin.template
   - systemd → ansible.builtin.systemd

2. `ansible/roles/monitoring_stack/tasks/main.yml` - 3 modules updated
   - file → ansible.builtin.file (2x)
   - synchronize → ansible.posix.synchronize (NOT ansible.builtin!)

3. `ansible/playbooks/vms/database.yml` pre_tasks block - 4 modules updated
   - apt → ansible.builtin.apt (2x)
   - apt_key → ansible.builtin.apt_key
   - apt_repository → ansible.builtin.apt_repository

### Key Learning
- `synchronize` module lives in `ansible.posix` collection, NOT `ansible.builtin`
- All other standard modules (apt, file, template, systemd, apt_key, apt_repository) are in `ansible.builtin`
- Syntax checks pass for database.yml and monitoring.yml
- media.yml has pre-existing error (missing checkmk.general.agent collection) unrelated to FQCN changes

### Verification
- ✅ database.yml --syntax-check: PASS
- ✅ monitoring.yml --syntax-check: PASS
- ⚠️ media.yml --syntax-check: FAIL (pre-existing, unrelated to FQCN)

## Story 5: Structural Cleanup (monitoring.yml + minecraft_server defaults)

**Completed**: 2026-03-17

### Part A: Move monitoring.yml
- Moved `ansible/playbooks/monitoring.yml` → `ansible/playbooks/vms/monitoring.yml`
- Syntax check passes

### Part B: minecraft_server parameterization
- Created `ansible/roles/minecraft_server/defaults/main.yml` with 5 variables:
  - `minecraft_server_user: minecraft`
  - `minecraft_server_group: minecraft`
  - `minecraft_server_home: /opt/minecraft`
  - `minecraft_server_java_package: temurin-21-jdk`
  - `minecraft_server_jar: server.jar`

- Updated `tasks/main.yml`: Replaced all hardcoded values with variables
  - `/opt/minecraft` → `{{ minecraft_server_home }}`
  - `minecraft` (user/group) → `{{ minecraft_server_user }}/{{ minecraft_server_group }}`
  - `temurin-21-jdk` → `{{ minecraft_server_java_package }}`

- Updated `templates/minecraft.service.j2`: Parameterized User, Group, WorkingDirectory, ExecStart, ExecStop

- Fixed indentation issues (3-space → 2-space) during edits
- Syntax checks pass for both playbooks

### Key Learnings
- Indentation consistency is critical in Ansible YAML
- Template files use Jinja2 syntax directly (no quotes needed around variables)
- All hardcoded paths/names should be in defaults/main.yml for role reusability

## Story 2 Follow-up: Terraform for_each migration (2026-03-17)

- Telmate/proxmox `nameserver` must stay as a top-level string attribute; set to `""` when not used to keep resource shape stable in a `for_each` refactor.
- `tailscale` originally omitted `swap`; mapping `swap = 0` and using `swap = each.value.swap > 0 ? each.value.swap : null` preserves behavior without forcing an invalid value.
- After `tofu state mv` from singleton resources to `proxmox_lxc.servers["<key>"]`, `tofu plan` can show only output diffs and no infrastructure destroy/recreate.
