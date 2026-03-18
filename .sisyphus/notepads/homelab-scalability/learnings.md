# Learnings

## Conventions (from prior refactor)
- OpenTofu binary: `tofu` (never `terraform`)
- Ansible runs from `ansible/` directory — ansible.cfg lives there
- All local hosts: `ansible_user: root` (become is always a no-op)
- Vault pattern: `vault.<vm_group>.<secret_name>`
- auto_tags plugin: every role gets an auto-generated tag matching its name
- FQCN: `ansible.builtin.*` for most, `ansible.posix.synchronize` for sync
- proxmox.yml: intentionally `gather_facts: false` — do NOT change
- Monitoring stack: docker compose up is intentionally commented out

## hostvars Pattern (Story 1)
- `hostvars['tools'].ansible_host` → 192.168.1.107
- `hostvars['authelia'].ansible_host` → 192.168.1.109
- Requires hosts to be in inventory AND play has gather_facts: true (or hosts already resolved)
- Actually works even without gather_facts because it reads from inventory, not facts

## Role Pattern
- Minimum: tasks/main.yml + defaults/main.yml
- Idiomatic: handlers/ if service restarts needed
- Docker roles: use community.docker.docker_container or docker_compose_v2

## Execution Order Rationale
- Story 3 first: portainer role creation + tools.yml modification
  → Story 4 syntax-check uses tools.yml (needs portainer role to exist)
- Story 1 independent of all Ansible changes
- Story 5 independent (Terraform only)
- Story 2 depends on Story 1 (uses hostvars refs from Story 1)
