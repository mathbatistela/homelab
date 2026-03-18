# Issues & Gotchas

## Story 2: Jinja2 in YAML values
traefik_services.yml contains Jinja2 expressions as YAML values (e.g., {{ traefik_local_domain }}).
These MUST be quoted in YAML to avoid parse errors:
  service_host: "budget.{{ traefik_local_domain }}"
  NOT: service_host: budget.{{ traefik_local_domain }}

## Story 2: include_role with loop
ansible.builtin.include_role in a loop requires `loop:` at the task level, not play level.
The `traefik_conf: "{{ item }}"` variable must be passed via `vars:` on the task.

## Story 5: Telmate/proxmox RC
As of 2026-03-17, Telmate/proxmox 3.0.2-rc01 was the latest available version.
Check https://registry.terraform.io/providers/Telmate/proxmox/latest before upgrading.
If no stable exists, add a comment documenting this.

## Known pre-existing issues (not fixing)
- ansible/plugins/callbacks/auto_tags.py: LSP error "Import ansible.plugins.callback could not be resolved" — no ansible venv locally, harmless
- pve_templates/defaults/main.yml: LSP "!vault unresolved tag" — no Ansible installed locally, harmless
