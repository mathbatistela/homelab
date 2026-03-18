.PHONY: lint syntax-check plan-home plan-cloud validate-home validate-cloud \
        play-infra play-database play-media play-minecraft play-tools \
        play-monitoring play-pangolin play-proxmox play-authelia play-tailscale

# ── Ansible ──────────────────────────────────────────────────────────────────

lint:
	cd ansible && ansible-lint playbooks/

syntax-check:
	cd ansible && \
	  ansible-playbook playbooks/vms/infra.yml --syntax-check && \
	  ansible-playbook playbooks/vms/database.yml --syntax-check && \
	  ansible-playbook playbooks/vms/media.yml --syntax-check && \
	  ansible-playbook playbooks/vms/minecraft.yml --syntax-check && \
	  ansible-playbook playbooks/vms/tools.yml --syntax-check && \
	  ansible-playbook playbooks/vms/monitoring.yml --syntax-check && \
	  ansible-playbook playbooks/vms/pangolin.yml --syntax-check && \
	  ansible-playbook playbooks/vms/authelia.yml --syntax-check && \
	  ansible-playbook playbooks/vms/tailscale.yml --syntax-check && \
	  ansible-playbook playbooks/nodes/proxmox.yml --syntax-check

play-infra:
	cd ansible && ansible-playbook playbooks/vms/infra.yml

play-database:
	cd ansible && ansible-playbook playbooks/vms/database.yml

play-media:
	cd ansible && ansible-playbook playbooks/vms/media.yml

play-minecraft:
	cd ansible && ansible-playbook playbooks/vms/minecraft.yml

play-tools:
	cd ansible && ansible-playbook playbooks/vms/tools.yml

play-monitoring:
	cd ansible && ansible-playbook playbooks/vms/monitoring.yml

play-pangolin:
	cd ansible && ansible-playbook playbooks/vms/pangolin.yml

play-authelia:
	cd ansible && ansible-playbook playbooks/vms/authelia.yml

play-tailscale:
	cd ansible && ansible-playbook playbooks/vms/tailscale.yml

play-proxmox:
	cd ansible && ansible-playbook playbooks/nodes/proxmox.yml

# ── Terraform ─────────────────────────────────────────────────────────────────

plan-home:
	cd terraform/home && tofu plan

plan-cloud:
	cd terraform/cloud && tofu plan

validate-home:
	cd terraform/home && tofu validate

validate-cloud:
	cd terraform/cloud && tofu validate
