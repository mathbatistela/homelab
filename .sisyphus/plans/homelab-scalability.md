# Homelab Scalability & Extensibility

**Created:** 2026-03-17
**Scope:** Eliminate hardcoded IPs, data-driven Traefik, Docker app patterns, Portainer extraction, Terraform hardening, CI pipeline

---

## Story 1: Eliminate hardcoded IPs from Traefik configs

**Files:** `ansible/playbooks/vms/infra.yml`, `ansible/inventories/local/hosts.yml`

### Context

Traefik service configs hardcode backend IPs:
- `http://192.168.1.107:5006` (tools — actual budget)
- `http://192.168.1.109:9091` (authelia)
- `https://192.168.1.107:9443` (tools — portainer)

If a host is re-IPed, these configs silently break. The IPs are already defined in `inventories/local/hosts.yml` as `ansible_host` — use `hostvars['<host>'].ansible_host` instead.

### Tasks

- [x] **1.1** In `infra.yml`, replace ALL hardcoded IPs with `hostvars` references:
  - `192.168.1.107` → `{{ hostvars['tools'].ansible_host }}`
  - `192.168.1.109` → `{{ hostvars['authelia'].ansible_host }}`
  Affected lines: 22, 54, 67, 99
- [x] **1.2** Verify that `infra.yml` plays have `gather_facts: true` (they do after our refactor) — required for `hostvars` to resolve cross-host vars
- [x] **1.3** Run `ansible-playbook playbooks/vms/infra.yml --syntax-check`
- [x] **1.4** Grep the entire `ansible/` directory for remaining hardcoded `192.168.1.` IPs in custom roles/playbooks (excluding inventory, geerlingguy.*, and Terraform). Report any remaining.

### Safety
- `hostvars['tools'].ansible_host` resolves to `192.168.1.107` — identical runtime behavior.
- Requires `gather_facts: true` on the play OR the host to be in inventory (it is).

### Acceptance Criteria
- Zero hardcoded `192.168.1.` IPs in `infra.yml`
- Syntax check passes
- Grep confirms no other hardcoded IPs in custom Ansible files

---

## Story 2: Data-driven Traefik service configuration

**Files:** `ansible/playbooks/vms/infra.yml`, `ansible/inventories/local/host_vars/infra/traefik_services.yml` (new)

### Context

`infra.yml` currently has 4 plays: 1 for Traefik install + 3 for individual service configs. Each new service requires copy-pasting an entire play block. This scales linearly and violates DRY.

Refactor to: one variable file listing all services, one play that loops over them.

### Tasks

- [x] **2.1** Create `ansible/inventories/local/host_vars/infra/traefik_services.yml` with a `traefik_services` list. Each entry captures one of the three current service configs:
- [x] **2.2** Refactor `infra.yml` to two plays:
- [x] **2.3** Verify the `configure_service.yml` task file already handles both `template:` and `content:` modes — it does (uses `when: traefik_conf.content is defined` and `when: traefik_conf.template is defined`). No changes needed to the role.
- [x] **2.4** Run `ansible-playbook playbooks/vms/infra.yml --syntax-check`
- [x] **2.5** Run `ansible-playbook playbooks/vms/infra.yml --check --diff --tags traefik_config` to verify the loop produces identical config files (dry-run mode, no actual changes)

### Safety
- The traefik role's `configure_service.yml` already supports both `template:` and `content:` modes via `when:` conditionals — the loop just calls it multiple times.
- `--check --diff` verifies the generated files match what's already deployed without making changes.
- Per-service tags are lost (replaced by single `traefik_config` tag) — acceptable tradeoff for DRY.

### Acceptance Criteria
- `infra.yml` reduced from 4 plays to 2 plays
- Adding a new Traefik service = adding one entry to `traefik_services.yml`
- Zero hardcoded IPs (uses `hostvars` from Story 1)
- Syntax check passes
- `--check --diff` shows no unexpected changes

---

## Story 3: Extract Portainer to its own role

**Files:** `ansible/playbooks/vms/tools.yml`, `ansible/roles/portainer/` (new)

### Context

`tools.yml` is the only playbook mixing role includes with inline `docker_container` tasks. Portainer should be a proper role following the same pattern as `actual_budget`.

### Tasks

- [x] **3.1** Create role directory: `ansible/roles/portainer/tasks/main.yml` and `ansible/roles/portainer/defaults/main.yml`
- [x] **3.2** `defaults/main.yml`:
- [x] **3.3** `tasks/main.yml` — move the inline task from `tools.yml` into it:
- [x] **3.4** Update `tools.yml` — replace inline tasks block with role include:
- [x] **3.5** Run `ansible-playbook playbooks/vms/tools.yml --syntax-check`

### Safety
- Identical runtime behavior — the role does exactly what the inline task did.
- `auto_tags` plugin will now auto-generate a `portainer` tag for the role.

### Acceptance Criteria
- `tools.yml` has zero inline `tasks:` blocks — roles only
- `portainer` role is reusable with configurable defaults
- Syntax check passes

---

## Story 4: Parameterize `actual_budget` role (missing defaults)

**Files:** `ansible/roles/actual_budget/defaults/main.yml` (new), `ansible/roles/actual_budget/tasks/main.yml`

### Context

`actual_budget` role hardcodes paths:
- `/mnt/homeshare/docker/actual-budget` (data dir)
- `/root/docker-compose-apps/actual-budget` (compose dir)

No `defaults/main.yml` exists. Follows the same pattern fixed for `minecraft_server` in the previous refactor.

### Tasks

- [x] **4.1** Create `ansible/roles/actual_budget/defaults/main.yml`:
- [x] **4.2** Update `tasks/main.yml` to use variables:
- [x] **4.3** Run `ansible-playbook playbooks/vms/tools.yml --syntax-check`

### Safety
- Defaults match current hardcoded values — zero runtime change.

### Acceptance Criteria
- `actual_budget` has `defaults/main.yml`
- Zero hardcoded paths in `tasks/main.yml`
- Syntax check passes

---

## Story 5: Terraform provider hardening

**Files:** `terraform/home/providers.tf`, `terraform/cloud/providers.tf`

### Context

- `Telmate/proxmox` pinned to `3.0.2-rc01` — a release candidate
- No `required_version` for OpenTofu itself in either module
- Cloud module uses mixed precision: `~> 5.5.0` (cloudflare) vs `~> 5.0` (aws)

### Tasks

- [x] **5.1** Check if `Telmate/proxmox` has a stable release newer than `3.0.2-rc01`. Search the provider registry for the latest version. If stable exists, pin to it. If not, keep the RC but add a comment: `# RC — no stable release available as of YYYY-MM-DD`
- [x] **5.2** Add `required_version` to both `terraform {}` blocks:
- [x] **5.3** Normalize cloud provider pinning: change `~> 5.0` (aws) to `~> 5.0.0` for consistent precision across all providers.
- [x] **5.4** Run `tofu validate` in both `terraform/home/` and `terraform/cloud/`

### Safety
- `required_version` only adds a constraint — doesn't change behavior if current `tofu` version already satisfies it.
- Provider version changes: if upgrading from RC to stable, run `tofu plan` to check for behavioral changes. Do NOT apply.

### Acceptance Criteria
- Both modules have `required_version`
- Provider version pinning is consistent (`~> X.Y.Z` pattern)
- `tofu validate` passes in both modules

---

## Story 6: Clean up orphaned hosts

**Files:** `ansible/inventories/local/hosts.yml`, `terraform/cloud/vms_dns.tf`

### Context

- `authelia` (109): in inventory + DNS, but no Terraform resource and no playbook
- `tailscale` (108): has Terraform resource + DNS, but NOT in inventory and no playbook

Both cause confusion about what's actually managed.

### Tasks

- [ ] **6.1** Decision point: for each host, decide disposition:
  - `authelia`: is it deployed? If yes, add a minimal playbook. If no, remove from inventory + DNS.
  - `tailscale`: is it deployed? If yes, add to inventory + create playbook. If no, remove Terraform resource + DNS.
  **THIS TASK REQUIRES USER INPUT — ask before proceeding.**
- [ ] **6.2** Based on decision, either:
  - (a) Create placeholder playbooks: `ansible/playbooks/vms/authelia.yml` and/or `ansible/playbooks/vms/tailscale.yml` with minimal structure (hosts + become + gather_facts + comment "# TODO: configure services")
  - (b) Remove orphaned entries from inventory/DNS/Terraform
- [ ] **6.3** If adding `tailscale` to inventory: add to `hosts.yml` under `proxmox` group with `ansible_host: 192.168.1.108`
- [ ] **6.4** Update `ansible/AGENTS.md` NOTES section to reflect resolved status of these hosts

### Safety
- Removing a Terraform resource for a running container would destroy it — only remove if confirmed not in use.
- Adding placeholder playbooks has zero runtime impact — they just document the host exists.
- Removing from inventory prevents accidental `ansible all` runs against undefined hosts.

### Acceptance Criteria
- Every host in inventory has a corresponding playbook (even if placeholder)
- Every host in Terraform has a corresponding inventory entry
- AGENTS.md notes updated
- No orphaned hosts

---

## Story 7: GitHub Actions CI pipeline

**Files:** `.github/workflows/lint.yml` (new)

### Tasks

- [x] **7.1** Create `.github/workflows/lint.yml`:
- [x] **7.2** Verify the workflow YAML is valid: `yamllint .github/workflows/lint.yml`
- [x] **7.3** Add `ansible-lint` and `yamllint` to `ansible/requirements.txt` (new file) for CI reproducibility:
  ```
  ansible-core>=2.15
  ansible-lint>=24.0
  yamllint>=1.35
  ```

### Safety
- CI is read-only — no `tofu apply`, no `ansible-playbook` runs against live hosts.
- `tofu init -backend=false` skips state backend — only downloads providers for validation.
- `continue-on-error: true` on yamllint makes it a soft gate initially.

### Acceptance Criteria
- Pipeline runs on push to main and PRs
- `syntax-check` validates all playbooks
- `tofu validate` checks both modules
- No secrets required — all validation is offline

---

## Execution Order & Dependencies

```
Story 1 (hardcoded IPs)       — no deps, do first
Story 4 (actual_budget defaults) — no deps, parallel with 1
Story 3 (portainer role)      — no deps, parallel with 1
Story 2 (data-driven traefik) — depends on Story 1 (uses hostvars)
Story 5 (terraform hardening) — independent, parallel with 1-4
Story 6 (orphaned hosts)      — REQUIRES USER INPUT, do after stories 1-5
Story 7 (CI pipeline)         — do last (tests final state)
```

## Out of Scope

- Docker base role abstraction (arr_stack, actual_budget, portainer share patterns — future refactor after Portainer role exists)
- Remote Terraform state backend (requires external infra — S3/Consul)
- Pre-commit hooks (CI covers linting; pre-commit is a nice-to-have on top)
- Molecule/idempotency testing (significant effort, future initiative)
- Single source of truth for VM definitions across Terraform/DNS/inventory (requires custom tooling or Terragrunt)
