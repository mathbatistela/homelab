# Issues & Gotchas

## Known Bugs Being Fixed
- `database.yml:47` — `invoice_ninja_user` uses `vault.database.n8n_user_pw` (should be `invoice_ninja_user_pw`)
- `database.yml` — `invoice_ninja_database` missing from `postgresql_databases` list

## Pre-existing (not fixing)
- `authelia` in inventory but no Terraform resource or playbook
- `tailscale` has Terraform resource (108) but no playbook
- `monitoring_stack` docker compose up commented out (intentional)
- LSP error on `auto_tags.py` (no ansible venv locally) — pre-existing, ignore

## Terraform State Risk
- Running `tofu state mv` modifies `terraform/home/terraform.tfstate` in place
- State backup created automatically by tofu at `terraform.tfstate.backup`
- If state mv fails mid-way, some resources may be at new addresses and some at old
- Recovery: use `tofu state mv` in reverse or restore from `.backup` file
