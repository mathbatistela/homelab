# Hermes

Hermes runs on the `hermes` VM (192.168.1.111) as a native install managed by systemd. It hosts both the WebUI (`hermes-webui`) and the gateway (`hermes-gateway`) for messaging platforms.

## Quick commands

```bash
# Deploy or reconfigure Hermes
make play-hermes

# Dry-run
make dry-run-hermes

# Check service status
ssh root@hermes systemctl status hermes-webui hermes-gateway

# Gateway logs
ssh root@hermes tail -f ~/.hermes/logs/gateway.log
```

## Development tooling

The Hermes playbook also applies the generic `dev_dependencies` role so the VM
has a useful development baseline. For this repo, that means base tools
(`git`, `make`, Python venv support, `rsync`, `jq`, `yq`, etc.), GitHub CLI
(`gh`), and the OpenTofu `tofu` CLI from the official OpenTofu apt repository.

Docker packages are available through the same role but disabled by default:

```yaml
dev_dependencies_install_docker: true
```

Only enable Docker after the Hermes LXC has the required nesting/runtime support.

## Email gateway (Zoho Mail)

Hermes can receive and reply to emails via IMAP/SMTP. The Zoho Mail account used here can be the same one used elsewhere in the homelab, but it is configured independently in the local Ansible vault.

Hermes manages its own **user-level** gateway service via `hermes gateway install`. The Ansible role does **not** install a system-level `hermes-gateway.service`; it only ensures any stale system unit is removed and restarts the user service after `.env` changes.

### Configuration

- **Role:** `ansible/roles/hermes/`
- **Host vars:** `ansible/inventories/local/host_vars/hermes/email.yml`
- **Password:** `vault.hermes.email_password` in `ansible/inventories/local/group_vars/all/vault.yml`

Set the Zoho app password:

```bash
cd ansible
ansible-vault edit inventories/local/group_vars/all/vault.yml
```

Example:

```yaml
vault:
  hermes:
    email_password: "<zoho-app-password>"
```

### Critical: do not overwrite `.env`

Hermes stores many secrets and runtime settings in `/root/.hermes/.env` (Discord bot token, ElevenLabs key, SearxNG URL, MCP keys, Firecrawl URL, etc.). The Ansible role **must not** template the entire file.

As a safety net, the role creates a timestamped backup of `.env` before any modification. Backups are kept in `~/.hermes/` with names like `.env.12345.2026-07-05@23:45:00~`.

The role uses `ansible.builtin.lineinfile` to manage only the email-related variables:

```yaml
EMAIL_ADDRESS
EMAIL_PASSWORD
EMAIL_IMAP_HOST
EMAIL_SMTP_HOST
EMAIL_IMAP_PORT
EMAIL_SMTP_PORT
EMAIL_POLL_INTERVAL
EMAIL_ALLOWED_USERS
EMAIL_HOME_ADDRESS
```

If you ever change how `.env` is written, make sure existing keys are preserved.

### Verification

After deploy, the gateway log should show:

```text
✓ discord connected
✓ email connected
Gateway running with 2 platform(s)
[Email] IMAP connection test passed
[Email] SMTP connection test passed
```

## WebUI

The WebUI runs the Hermes agent in-process and is exposed through Traefik (local) and Pangolin (public). It binds to `0.0.0.0:8787`. Access is gated by Authelia/Pangolin SSO; no built-in WebUI password is set.
