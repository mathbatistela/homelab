# Decisions

## 2026-03-18 — Branch strategy
Branch: scalability/homelab-iac on main worktree path.
Reason: Terraform state files are gitignored — separate worktree would not have them.

## 2026-03-18 — Story 6 gate
Story 6 REQUIRES USER INPUT before execution.
Questions:
1. authelia (109): Is it deployed? → add playbook OR remove from inventory+DNS
2. tailscale (108): Is it deployed? → add to inventory+playbook OR remove Terraform+DNS
Do NOT proceed with Story 6 until user answers.

## 2026-03-18 — hostvars vs hardcoded IPs
Using hostvars['host'].ansible_host is the correct Ansible idiom.
It references inventory values, not gathered facts — works regardless of gather_facts setting.
Requires the target host to be in inventory (authelia and tools are).
