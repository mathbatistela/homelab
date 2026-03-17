# Homelab IaC Refactor & Hardening

**Created:** 2026-03-17
**Scope:** Bug fix, Terraform DRY, Ansible consistency, structural cleanup, quality tooling

---

## Story 1: Fix database.yml copy-paste bug

**Files:** `ansible/playbooks/vms/database.yml`

### Tasks

- [x] **1.1** Fix `invoice_ninja_user` password: change `vault.database.n8n_user_pw` to `vault.database.invoice_ninja_user_pw` on line 47
- [x] **1.2** Add missing database entry to `postgresql_databases` list:
  ```yaml
  - name: invoice_ninja_database
    owner: invoice_ninja_user
  ```
  Insert after line 63 (localiza_database entry), before the closing of `postgresql_databases`
- [x] **1.3** Verify vault has `vault.database.invoice_ninja_user_pw` defined. If not, note it must be added via `ansible-vault edit inventories/local/group_vars/all/vault.yml`
- [x] **1.4** Run `ansible-playbook playbooks/vms/database.yml --syntax-check` from `ansible/` dir

### Acceptance Criteria
- `invoice_ninja_user` references its own vault password
- `invoice_ninja_database` exists with correct owner
- Syntax check passes

---

## Story 2: Terraform DRY — refactor LXC resources to for_each

**Files:** `terraform/home/main.tf`, `terraform/home/outputs.tf`

### Context

Six `proxmox_lxc` resources repeat near-identical blocks. Refactor to a single `proxmox_lxc.servers` resource with `for_each` over a locals map. Resource address changes from `proxmox_lxc.media_server` to `proxmox_lxc.servers["media"]`, which requires `tofu state mv` BEFORE apply to avoid destroy/recreate.

### Current resources → map keys

| Current Resource | Map Key | VMID | IP | Cores | Memory | Swap | Disk | Extras |
|---|---|---|---|---|---|---|---|---|
| `proxmox_lxc.media_server` | `media` | 101 | 192.168.1.101 | 2 | 4096 | 1024 | 16G | — |
| `proxmox_lxc.infra_server` | `infra` | 102 | 192.168.1.102 | 2 | 4096 | 512 | 16G | — |
| `proxmox_lxc.database_server` | `database` | 103 | 192.168.1.103 | 2 | 4096 | 1024 | 32G | nameserver = "1.1.1.1 8.8.8.8" |
| `proxmox_lxc.minecraft_server` | `minecraft` | 105 | 192.168.1.105 | 4 | 8192 | 2048 | 50G | — |
| `proxmox_lxc.tools_server` | `tools` | 107 | 192.168.1.107 | 2 | 8192 | 2048 | 50G | mountpoint block |
| `proxmox_lxc.tailscale_server` | `tailscale` | 108 | 192.168.1.108 | 1 | 512 | 0 (unset) | 5G | — |

### Tasks

- [x] **2.1** Create `locals.servers` map in `main.tf` with all 6 servers. Each entry must capture: vmid, hostname, cores, memory, swap (optional, default null), disk_size, nameserver (optional, default null), mountpoints (optional, default [])
- [x] **2.2** Create single `resource "proxmox_lxc" "servers"` with `for_each = local.servers`. Use `each.value.<field>` for all attributes. Handle optional fields with `dynamic` blocks:
  - `mountpoint` block: only for tools server (use `dynamic "mountpoint"`)
  - `nameserver`: only for database (use conditional)
  - `swap`: omit attribute when null/0 (tailscale has no swap set)
- [x] **2.3** Refactor `outputs.tf` to use `for` expression outputting a map of all servers, or individual outputs using `proxmox_lxc.servers["<key>"]`
- [x] **2.4** Run all 6 `tofu state mv` commands directly from `terraform/home/`. Each must exit 0 before proceeding to the next:
  ```bash
  cd terraform/home
  tofu state mv 'proxmox_lxc.media_server' 'proxmox_lxc.servers["media"]'
  tofu state mv 'proxmox_lxc.infra_server' 'proxmox_lxc.servers["infra"]'
  tofu state mv 'proxmox_lxc.database_server' 'proxmox_lxc.servers["database"]'
  tofu state mv 'proxmox_lxc.minecraft_server' 'proxmox_lxc.servers["minecraft"]'
  tofu state mv 'proxmox_lxc.tools_server' 'proxmox_lxc.servers["tools"]'
  tofu state mv 'proxmox_lxc.tailscale_server' 'proxmox_lxc.servers["tailscale"]'
  ```
  If any command fails, STOP — fix the code or state issue before continuing.
- [x] **2.5** Run `tofu plan` from `terraform/home/` and verify the output shows ZERO resource destroys or recreates. Only in-place updates (`~`) or no changes are acceptable. If any `+`/`-` destroy/recreate appears, the refactor is wrong — stop and fix before proceeding. Do NOT run `tofu apply`.

### Acceptance Criteria
- `main.tf` has ONE `proxmox_lxc.servers` resource with `for_each`
- `locals.servers` map captures ALL per-server differences (cores, memory, swap, disk, nameserver, mountpoints)
- `outputs.tf` references new resource addresses
- All 6 `tofu state mv` commands executed successfully (exit 0)
- `tofu plan` shows ZERO destroys or recreates — only `~` in-place updates or "No changes"
- No attributes lost or changed vs current definitions — diff the generated HCL attributes against original per-server blocks
- CRITICAL: `tofu validate` passes on the refactored code (can run without state)

---

## Story 3: Ansible FQCN standardization

**Files:**
- `ansible/roles/samba_share/tasks/main.yml` (uses `apt:`, `file:`, `template:`, `systemd:`)
- `ansible/roles/monitoring_stack/tasks/main.yml` (uses `file:`, `synchronize:`)
- `ansible/playbooks/vms/database.yml` (pre_tasks use `apt:`, `apt_key:`, `apt_repository:`)

### Tasks

- [x] **3.1** `samba_share/tasks/main.yml`: Replace short module names with FQCN:
  - `apt:` → `ansible.builtin.apt:`
  - `file:` → `ansible.builtin.file:`
  - `template:` → `ansible.builtin.template:`
  - `systemd:` → `ansible.builtin.systemd:`
- [x] **3.2** `monitoring_stack/tasks/main.yml`: Replace:
  - `file:` → `ansible.builtin.file:`
  - `synchronize:` → `ansible.posix.synchronize:` (note: synchronize is in `ansible.posix`, NOT `ansible.builtin`)
- [x] **3.3** `database.yml` pre_tasks block (lines 14-31): Replace:
  - `apt:` → `ansible.builtin.apt:` (lines 14, 30)
  - `apt_key:` → `ansible.builtin.apt_key:` (line 19)
  - `apt_repository:` → `ansible.builtin.apt_repository:` (line 25)
- [x] **3.4** Run syntax check on all three affected playbooks:
  ```bash
  cd ansible
  ansible-playbook playbooks/vms/database.yml --syntax-check
  ansible-playbook playbooks/vms/media.yml --syntax-check  # uses samba_share
  ansible-playbook playbooks/monitoring.yml --syntax-check  # uses monitoring_stack
  ```

### Acceptance Criteria
- Zero short module names in custom roles/playbooks (excluding vendored geerlingguy.* roles)
- All three syntax checks pass
- `synchronize` correctly uses `ansible.posix.synchronize`, not `ansible.builtin`

---

## Story 4: Ansible playbook consistency (become/gather_facts)

**Files:** All playbooks in `ansible/playbooks/vms/` and `ansible/playbooks/`

### Context — Current state

| Playbook | become | gather_facts | Notes |
|---|---|---|---|
| `infra.yml` | Play 1 only (traefik install) | Play 1 only | Other plays are task-only (traefik config) |
| `database.yml` | Plays 1,2,3 | None explicit | — |
| `media.yml` | Plays 1,2 | Plays 1,2 | Play 3 (checkmk) has neither |
| `minecraft.yml` | None (tasks use per-task `become: yes`) | `false` | — |
| `tools.yml` | None at play level | None | Tasks use per-task become |
| `pangolin.yml` | Plays 1,2 | None | — |
| `monitoring.yml` | None | None | — |
| `proxmox.yml` | None | `false` x2 | — |

### Safety analysis before changes

- All local hosts connect as `ansible_user: root` per inventory. Adding `become: true` when already root is a no-op.
- `gather_facts: true` is the Ansible default. Making it explicit changes nothing.
- `minecraft.yml` uses per-task `become: yes` — adding play-level `become: true` makes per-task `become` redundant but harmless.
- `proxmox.yml` explicitly sets `gather_facts: false` — do NOT change (intentional, PVE node may not have Python for fact gathering).
- Traefik config plays in `infra.yml` (plays 2-4) are task-only and target infra — safe to add `become: true`.
- `monitoring.yml` targets `infra` host — safe to add `become: true`.
- `media.yml` play 3 (checkmk_agent) uses `checkmk.general.agent` collection role — safe to add `become: true` (role expects it).

### Tasks

- [x] **4.1** `minecraft.yml`: Add `become: true` and `gather_facts: true` at play level. Remove per-task `become: yes` from all tasks in `minecraft_server/tasks/main.yml` (there are 12 occurrences)
- [x] **4.2** `tools.yml`: Add `become: true` and `gather_facts: true` at play level
- [x] **4.3** `monitoring.yml`: Add `become: true` and `gather_facts: true` at play level
- [x] **4.4** `database.yml`: Add explicit `gather_facts: true` to all three plays
- [x] **4.5** `pangolin.yml`: Add explicit `gather_facts: true` to both plays
- [x] **4.6** `infra.yml`: Add `become: true` and `gather_facts: true` to plays 2-4 (traefik config plays, lines 8, 24, 67)
- [x] **4.7** `media.yml` play 3 (checkmk): Add `become: true` and `gather_facts: true`
- [x] **4.8** Do NOT touch `proxmox.yml` — `gather_facts: false` is intentional
- [x] **4.9** Run syntax check on ALL modified playbooks:
  ```bash
  cd ansible
  for pb in infra database media minecraft tools pangolin monitoring; do
    ansible-playbook playbooks/vms/${pb}.yml --syntax-check 2>/dev/null || \
    ansible-playbook playbooks/${pb}.yml --syntax-check
  done
  ```

### Acceptance Criteria
- Every play in every playbook has explicit `become:` and `gather_facts:` (except `proxmox.yml` which keeps `gather_facts: false` and no become)
- `minecraft_server/tasks/main.yml` has zero per-task `become: yes` (now inherited from play)
- All syntax checks pass
- NO behavioral change — all plays already ran as root, facts were already gathered by default

---

## Story 5: Structural cleanup

### 5A: Move monitoring.yml

- [x] **5A.1** Move `ansible/playbooks/monitoring.yml` to `ansible/playbooks/vms/monitoring.yml`
- [x] **5A.2** Verify syntax: `ansible-playbook playbooks/vms/monitoring.yml --syntax-check`

### 5B: Add defaults/main.yml for pve_storage

**File to create:** `ansible/roles/pve_storage/defaults/main.yml`

Variables used in `pve_storage/tasks/main.yml` but currently undefined in defaults:
- `pve_iso_storage`
- `pve_storage_path_iso`
- `pve_snippets_storage`
- `pve_storage_path_snippets`
- `pve_template_storage`
- `pve_storage_path_templates`
- `pve_lxc_template_storage`
- `pve_storage_path_lxc_templates`

- [x] **5B.1** Check if these variables are defined elsewhere (host_vars, group_vars, or passed inline). Search for their definitions across inventory
- [x] **5B.2** Create `ansible/roles/pve_storage/defaults/main.yml` with sensible defaults matching current usage. Follow the naming pattern from sibling roles (`pve_homeshare`, `pve_vmstorage`):
  ```yaml
  pve_iso_storage: "iac-iso"
  pve_storage_path_iso: "/mnt/iso_storage"
  pve_snippets_storage: "iac-snippets"
  pve_storage_path_snippets: "/mnt/snippets"
  pve_template_storage: "iac-templates"
  pve_storage_path_templates: "/mnt/templates"
  pve_lxc_template_storage: "iac-lxc-templates"
  pve_storage_path_lxc_templates: "/mnt/lxc_templates"
  ```
  IMPORTANT: These values MUST match whatever the current runtime uses. If variables are defined in inventory/group_vars, use those exact values as defaults. If undefined and relying on command-line or env, flag to the user.

### 5C: Add defaults/main.yml for minecraft_server

**File to create:** `ansible/roles/minecraft_server/defaults/main.yml`

The role hardcodes paths and values in tasks. Extract to defaults:

- [x] **5C.1** Create `ansible/roles/minecraft_server/defaults/main.yml`:
  ```yaml
  minecraft_server_user: minecraft
  minecraft_server_group: minecraft
  minecraft_server_home: /opt/minecraft
  minecraft_server_java_package: temurin-21-jdk
  minecraft_server_jar: server.jar
  ```
- [x] **5C.2** Update `minecraft_server/tasks/main.yml` to reference these variables instead of hardcoded values. Replace:
  - `/opt/minecraft` → `{{ minecraft_server_home }}`
  - `minecraft` (user/group) → `{{ minecraft_server_user }}` / `{{ minecraft_server_group }}`
  - `temurin-21-jdk` → `{{ minecraft_server_java_package }}`
- [x] **5C.3** Also update `minecraft_server/templates/minecraft.service.j2` if it references hardcoded paths
- [x] **5C.4** Run syntax check: `ansible-playbook playbooks/vms/minecraft.yml --syntax-check`

### 5D: Extract checkmk_agent repeated config

The `checkmk_agent/tasks/main.yml` repeats `server_url`, `site`, `automation_user`, `automation_secret` in 4 task blocks (lines 16-19, 27-30, 36-39, 72-75).

- [x] **5D.1** Add derived variables to `checkmk_agent/defaults/main.yml`:
  ```yaml
  checkmk_server_url: "{{ checkmk_settings.server.protocol }}://{{ checkmk_settings.server.address }}:{{ checkmk_settings.server.port }}"
  checkmk_automation_user: "{{ checkmk_settings.server.user_automation }}"
  checkmk_automation_secret: "{{ checkmk_settings.server.user_automation_secret }}"
  checkmk_site: "{{ checkmk_settings.agent.site }}"
  ```
- [x] **5D.2** Update `checkmk_agent/tasks/main.yml` to use the short variable names:
  - `server_url: "{{ checkmk_server_url }}"` (4 occurrences)
  - `site: "{{ checkmk_site }}"` (4 occurrences)
  - `automation_user: "{{ checkmk_automation_user }}"` (4 occurrences)
  - `automation_secret: "{{ checkmk_automation_secret }}"` (4 occurrences)
- [x] **5D.3** Run syntax check: `ansible-playbook playbooks/vms/media.yml --syntax-check`

### Acceptance Criteria
- `monitoring.yml` lives in `playbooks/vms/`
- `pve_storage` and `minecraft_server` have `defaults/main.yml`
- `minecraft_server` tasks use variables, not hardcoded values
- `checkmk_agent` tasks reference short derived variable names (4 occurrences each reduced to 1 definition)
- All syntax checks pass

---

## Story 6: Quality tooling

**Files to create:** `ansible/.yamllint.yml`, `ansible/.ansible-lint`, `Makefile`

### Tasks

- [x] **6.1** Create `ansible/.yamllint.yml`:
- [x] **6.2** Create `ansible/.ansible-lint`:
- [x] **6.3** Create root `Makefile` with targets:
- [x] **6.4** Run `make lint` and `make syntax-check` to verify all targets work. Note any pre-existing lint issues but do NOT fix them in this story.

### Acceptance Criteria
- `make lint` runs ansible-lint and yamllint (excluding vendored roles)
- `make syntax-check` validates all playbooks
- `make plan-home` and `make plan-cloud` work from repo root
- `make play-<vm>` shortcuts work for all VMs

---

## Execution Order & Dependencies

```
Story 1 (bug fix)          — no deps, do first
Story 3 (FQCN)            — no deps, can parallel with 1
Story 4 (become/facts)     — no deps, can parallel with 1,3
Story 5A (move monitoring) — do before Story 6 (Makefile references new path)
Story 5B (pve_storage)     — no deps
Story 5C (minecraft)       — depends on Story 4.1 (become removal)
Story 5D (checkmk)         — no deps
Story 2 (Terraform DRY)    — independent, can parallel with all Ansible stories
Story 6 (quality)          — do last (references final file paths)
```

## Out of Scope

- `authelia` / `tailscale` gaps (infrastructure not provisioned)
- Portainer extraction to role (low value)
- Remote state backend (acceptable for homelab)
- CI/CD pipeline (future scope)
- Vendored role updates (geerlingguy.*)
