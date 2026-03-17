# Decisions

## 2026-03-17 — Worktree Strategy
Working on branch `refactor/homelab-iac` in main repo path `/home/mbatistela/personal/programming/homelab`.
Reason: Terraform state files are gitignored — a separate worktree would not have them.
All `tofu state mv` commands must run from `terraform/home/` against live local state.

## 2026-03-17 — Story 2: Agent runs tofu state mv
User explicitly requested the agent handle state migration commands (not generate a MIGRATION.md).
Agent must run all 6 `tofu state mv` commands before running `tofu plan`.
Do NOT run `tofu apply` — user reviews plan output.

## 2026-03-17 — Story 3: synchronize FQCN
`synchronize` is in `ansible.posix` collection, not `ansible.builtin`. Must use `ansible.posix.synchronize`.

## 2026-03-17 — Execution Order
1→3→(4+5B+5D parallel)→(5A+5C after 4)→2→6
Stories 1 and 3 are sequential (both touch database.yml).

## 2026-03-17 — Story 2 implementation shape
Refactor `terraform/home/main.tf` to one `proxmox_lxc.servers` resource with `for_each` over `local.servers`.
State migration is mandatory via 6 `tofu state mv` commands to avoid destroy/recreate from address changes.
Outputs are consolidated into one `servers` map output for key-address parity with `for_each` keys.
