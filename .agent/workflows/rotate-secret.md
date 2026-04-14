# Workflow: Rotate a secret

## Steps
1. Identify the vault file:
   - Local secrets: `ansible/inventories/local/group_vars/all/vault.yml`
   - Cloud secrets: `ansible/inventories/cloud/group_vars/all/vault.yml`

2. Ensure `ansible/vault.auth` exists.

3. Edit the vault:
   ```bash
   ansible-vault edit ansible/inventories/local/group_vars/all/vault.yml \
     --vault-password-file ansible/vault.auth
   ```

4. Update the secret value. Keep the variable path convention:
   `vault.<group>.<secret_name>`.

5. Run a dry-run of affected playbooks:
   ```bash
   make dry-run-<host>
   ```

6. Apply the playbook that consumes the secret:
   ```bash
   make play-<host>
   ```

7. Verify the service still starts correctly.

8. Log the run:
   ```bash
   make agent-log TARGET=rotate-secret STATUS=done
   ```

## Safety
- **Never** commit `vault.auth`
- **Never** paste decrypted vault contents into chat
- If unsure which playbooks are affected, grep for the variable name
