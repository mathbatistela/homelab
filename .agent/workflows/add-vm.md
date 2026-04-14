# Workflow: Add a new VM

## Pre-flight
1. Run `make check` to ensure the repo is in a clean state.

## Steps
1. **Edit `config/network.json`**
   - Add the new hostname and IP under `local_hosts`.
   - Follow convention: IP = `192.168.1.{100+}`, VMID = last octet.

2. **Edit `terraform/home/main.tf`**
   - Add the VM to the `local.servers` map.
   - Do **not** hardcode the IP; reference `local.network.local_hosts.<name>`.

3. **Run Terraform plan**
   - `make plan-home`
   - Review output carefully.

4. **Apply Terraform**
   - `make apply-home`

5. **Add DNS (if public)**
   - Edit `terraform/cloud/vms_dns.tf` to add an A record if needed.
   - `make plan-cloud && make apply-cloud`

6. **Create Ansible playbook**
   - `ansible/playbooks/vms/<host>.yml`
   - Follow existing playbook structure (multiple plays, tags per play/role).

7. **Update `AGENTS.md`**
   - Add the new host to the NETWORK MAP table.

8. **Run validation**
   - `make check`
   - `make syntax-check`

9. **Log the run**
   - `make agent-log TARGET=add-vm STATUS=done`
