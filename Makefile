.PHONY: bootstrap doctor lint syntax-check validate \
        plan-home plan-cloud validate-home validate-cloud apply-home apply-cloud \
        play-infra play-database play-media play-minecraft play-tools \
        play-monitoring play-pangolin play-proxmox play-authelia play-tailscale \
        deploy-vm deploy-services deploy-blueprint

VENV := .venv
PYTHON := $(VENV)/bin/python3
PIP := $(VENV)/bin/pip
ANSIBLE_PLAYBOOK := $(VENV)/bin/ansible-playbook
ANSIBLE_LINT := $(VENV)/bin/ansible-lint
ANSIBLE_GALAXY := $(VENV)/bin/ansible-galaxy

$(VENV)/bin/python3:
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -r ansible/requirements.txt

# ── Bootstrap & health checks ────────────────────────────────────────────────

bootstrap: $(VENV)/bin/python3
	cd ansible && ../$(ANSIBLE_GALAXY) collection install -r requirements.yml -p collections

doctor: $(VENV)/bin/python3
	@test -f ansible/vault.auth || (printf 'Missing ansible/vault.auth\n' && exit 1)
	@test -x $(ANSIBLE_PLAYBOOK) || (printf 'Missing $(ANSIBLE_PLAYBOOK)\n' && exit 1)
	@test -x $(ANSIBLE_LINT) || (printf 'Missing $(ANSIBLE_LINT)\n' && exit 1)
	@test -x $(ANSIBLE_GALAXY) || (printf 'Missing $(ANSIBLE_GALAXY)\n' && exit 1)
	@test -d ansible/collections/ansible_collections/community/general || (printf 'Missing community.general collection. Run make bootstrap\n' && exit 1)
	@test -d ansible/collections/ansible_collections/community/docker || (printf 'Missing community.docker collection. Run make bootstrap\n' && exit 1)
	@test -d ansible/collections/ansible_collections/community/postgresql || (printf 'Missing community.postgresql collection. Run make bootstrap\n' && exit 1)
	@test -d ansible/collections/ansible_collections/ansible/posix || (printf 'Missing ansible.posix collection. Run make bootstrap\n' && exit 1)
	@command -v tofu >/dev/null 2>&1 || (printf 'Missing tofu binary\n' && exit 1)
	@printf 'Doctor OK\n'

# ── Ansible ──────────────────────────────────────────────────────────────────

lint: $(VENV)/bin/python3
	cd ansible && ../$(ANSIBLE_LINT) --offline playbooks/

validate: $(VENV)/bin/python3
	$(PYTHON) scripts/validate_sources.py

syntax-check: $(VENV)/bin/python3
	cd ansible && \
	  ../$(ANSIBLE_PLAYBOOK) -i inventories/local playbooks/vms/infra.yml --syntax-check && \
	  ../$(ANSIBLE_PLAYBOOK) -i inventories/local playbooks/vms/database.yml --syntax-check && \
	  ../$(ANSIBLE_PLAYBOOK) -i inventories/local playbooks/vms/media.yml --syntax-check && \
	  ../$(ANSIBLE_PLAYBOOK) -i inventories/local playbooks/vms/minecraft.yml --syntax-check && \
	  ../$(ANSIBLE_PLAYBOOK) -i inventories/local playbooks/vms/tools.yml --syntax-check && \
	  ../$(ANSIBLE_PLAYBOOK) -i inventories/local playbooks/vms/monitoring.yml --syntax-check && \
	  ../$(ANSIBLE_PLAYBOOK) -i inventories/local -i inventories/cloud playbooks/vms/pangolin.yml --syntax-check && \
	  ../$(ANSIBLE_PLAYBOOK) -i inventories/local playbooks/vms/authelia.yml --syntax-check && \
	  ../$(ANSIBLE_PLAYBOOK) -i inventories/local playbooks/vms/tailscale.yml --syntax-check && \
	  ../$(ANSIBLE_PLAYBOOK) -i inventories/local playbooks/nodes/proxmox.yml --syntax-check

play-infra: $(VENV)/bin/python3
	cd ansible && ../$(ANSIBLE_PLAYBOOK) -i inventories/local playbooks/vms/infra.yml

play-database: $(VENV)/bin/python3
	cd ansible && ../$(ANSIBLE_PLAYBOOK) -i inventories/local playbooks/vms/database.yml

play-media: $(VENV)/bin/python3
	cd ansible && ../$(ANSIBLE_PLAYBOOK) -i inventories/local playbooks/vms/media.yml

play-minecraft: $(VENV)/bin/python3
	cd ansible && ../$(ANSIBLE_PLAYBOOK) -i inventories/local playbooks/vms/minecraft.yml

play-tools: $(VENV)/bin/python3
	cd ansible && ../$(ANSIBLE_PLAYBOOK) -i inventories/local playbooks/vms/tools.yml

play-monitoring: $(VENV)/bin/python3
	cd ansible && ../$(ANSIBLE_PLAYBOOK) -i inventories/local playbooks/vms/monitoring.yml

play-pangolin: $(VENV)/bin/python3
	cd ansible && ../$(ANSIBLE_PLAYBOOK) -i inventories/local -i inventories/cloud playbooks/vms/pangolin.yml

play-authelia: $(VENV)/bin/python3
	cd ansible && ../$(ANSIBLE_PLAYBOOK) -i inventories/local playbooks/vms/authelia.yml

play-tailscale: $(VENV)/bin/python3
	cd ansible && ../$(ANSIBLE_PLAYBOOK) -i inventories/local playbooks/vms/tailscale.yml

play-proxmox: $(VENV)/bin/python3
	cd ansible && ../$(ANSIBLE_PLAYBOOK) -i inventories/local playbooks/nodes/proxmox.yml

# ── Terraform ─────────────────────────────────────────────────────────────────

plan-home:
	cd terraform/home && tofu plan

plan-cloud:
	cd terraform/cloud && tofu plan

validate-home:
	cd terraform/home && tofu validate

validate-cloud:
	cd terraform/cloud && tofu validate

apply-home:
	cd terraform/home && tofu apply

apply-cloud:
	cd terraform/cloud && tofu apply

# ── Composite targets ────────────────────────────────────────────────────────

deploy-vm: $(VENV)/bin/python3
ifndef VM
	$(error VM is required. Usage: make deploy-vm VM=docs)
endif
	$(MAKE) apply-home
	$(MAKE) apply-cloud
	cd ansible && ../$(ANSIBLE_PLAYBOOK) -i inventories/local playbooks/vms/$(VM).yml

deploy-services: $(VENV)/bin/python3
	$(MAKE) play-infra
	$(MAKE) play-pangolin
	$(MAKE) play-monitoring

deploy-blueprint: $(VENV)/bin/python3
	cd ansible && ../$(ANSIBLE_PLAYBOOK) -i inventories/local -i inventories/cloud playbooks/vms/pangolin.yml --tags pangolin
	$(MAKE) play-monitoring
