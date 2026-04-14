.PHONY: bootstrap doctor lint syntax-check validate check lint-agents check-network fix-network \
        plan-home plan-cloud plan-all validate-home validate-cloud apply-home apply-cloud apply-all \
        play-infra play-database play-media play-minecraft play-tools \
        play-monitoring play-pangolin play-proxmox play-authelia play-tailscale \
        dry-run-infra dry-run-database dry-run-media dry-run-minecraft dry-run-tools \
        dry-run-monitoring dry-run-pangolin dry-run-proxmox dry-run-authelia dry-run-tailscale \
        deploy-vm deploy-services deploy-blueprint \
        add-vm add-service rotate-secret \
        apps-list apps-validate apps-build apps-create agent-log agent-decision

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

# ── Validation gates ─────────────────────────────────────────────────────────

check: $(VENV)/bin/python3
	cd terraform/home && tofu init -backend=false && tofu validate
	cd terraform/cloud && tofu init -backend=false && tofu validate
	$(PYTHON) scripts/validate_sources.py
	$(PYTHON) scripts/lint_agents.py
	$(PYTHON) scripts/check_network.py
	$(MAKE) syntax-check

lint-agents: $(VENV)/bin/python3
	$(PYTHON) scripts/lint_agents.py

check-network: $(VENV)/bin/python3
	$(PYTHON) scripts/check_network.py

fix-network: $(VENV)/bin/python3
	$(PYTHON) scripts/fix_network.py

validate: $(VENV)/bin/python3
	$(PYTHON) scripts/validate_sources.py

# ── Ansible ──────────────────────────────────────────────────────────────────

lint: $(VENV)/bin/python3
	cd ansible && ../$(ANSIBLE_LINT) --offline playbooks/

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
	@$(PYTHON) scripts/log_agent_run.py $@ done

play-database: $(VENV)/bin/python3
	cd ansible && ../$(ANSIBLE_PLAYBOOK) -i inventories/local playbooks/vms/database.yml
	@$(PYTHON) scripts/log_agent_run.py $@ done

play-media: $(VENV)/bin/python3
	cd ansible && ../$(ANSIBLE_PLAYBOOK) -i inventories/local playbooks/vms/media.yml
	@$(PYTHON) scripts/log_agent_run.py $@ done

play-minecraft: $(VENV)/bin/python3
	cd ansible && ../$(ANSIBLE_PLAYBOOK) -i inventories/local playbooks/vms/minecraft.yml
	@$(PYTHON) scripts/log_agent_run.py $@ done

play-tools: $(VENV)/bin/python3
	cd ansible && ../$(ANSIBLE_PLAYBOOK) -i inventories/local playbooks/vms/tools.yml
	@$(PYTHON) scripts/log_agent_run.py $@ done

play-monitoring: $(VENV)/bin/python3
	cd ansible && ../$(ANSIBLE_PLAYBOOK) -i inventories/local playbooks/vms/monitoring.yml
	@$(PYTHON) scripts/log_agent_run.py $@ done

play-pangolin: $(VENV)/bin/python3
	cd ansible && ../$(ANSIBLE_PLAYBOOK) -i inventories/local -i inventories/cloud playbooks/vms/pangolin.yml
	@$(PYTHON) scripts/log_agent_run.py $@ done

play-authelia: $(VENV)/bin/python3
	cd ansible && ../$(ANSIBLE_PLAYBOOK) -i inventories/local playbooks/vms/authelia.yml
	@$(PYTHON) scripts/log_agent_run.py $@ done

play-tailscale: $(VENV)/bin/python3
	cd ansible && ../$(ANSIBLE_PLAYBOOK) -i inventories/local playbooks/vms/tailscale.yml
	@$(PYTHON) scripts/log_agent_run.py $@ done

play-proxmox: $(VENV)/bin/python3
	cd ansible && ../$(ANSIBLE_PLAYBOOK) -i inventories/local playbooks/nodes/proxmox.yml
	@$(PYTHON) scripts/log_agent_run.py $@ done

# ── Ansible dry-run (check mode) ─────────────────────────────────────────────

dry-run-infra: $(VENV)/bin/python3
	cd ansible && ../$(ANSIBLE_PLAYBOOK) -i inventories/local playbooks/vms/infra.yml --check --diff

dry-run-database: $(VENV)/bin/python3
	cd ansible && ../$(ANSIBLE_PLAYBOOK) -i inventories/local playbooks/vms/database.yml --check --diff

dry-run-media: $(VENV)/bin/python3
	cd ansible && ../$(ANSIBLE_PLAYBOOK) -i inventories/local playbooks/vms/media.yml --check --diff

dry-run-minecraft: $(VENV)/bin/python3
	cd ansible && ../$(ANSIBLE_PLAYBOOK) -i inventories/local playbooks/vms/minecraft.yml --check --diff

dry-run-tools: $(VENV)/bin/python3
	cd ansible && ../$(ANSIBLE_PLAYBOOK) -i inventories/local playbooks/vms/tools.yml --check --diff

dry-run-monitoring: $(VENV)/bin/python3
	cd ansible && ../$(ANSIBLE_PLAYBOOK) -i inventories/local playbooks/vms/monitoring.yml --check --diff

dry-run-pangolin: $(VENV)/bin/python3
	cd ansible && ../$(ANSIBLE_PLAYBOOK) -i inventories/local -i inventories/cloud playbooks/vms/pangolin.yml --check --diff

dry-run-authelia: $(VENV)/bin/python3
	cd ansible && ../$(ANSIBLE_PLAYBOOK) -i inventories/local playbooks/vms/authelia.yml --check --diff

dry-run-tailscale: $(VENV)/bin/python3
	cd ansible && ../$(ANSIBLE_PLAYBOOK) -i inventories/local playbooks/vms/tailscale.yml --check --diff

dry-run-proxmox: $(VENV)/bin/python3
	cd ansible && ../$(ANSIBLE_PLAYBOOK) -i inventories/local playbooks/nodes/proxmox.yml --check --diff

# ── Terraform ─────────────────────────────────────────────────────────────────

plan-home:
	cd terraform/home && tofu plan

plan-cloud:
	cd terraform/cloud && tofu plan

plan-all: plan-home plan-cloud

validate-home:
	cd terraform/home && tofu validate

validate-cloud:
	cd terraform/cloud && tofu validate

apply-home:
	cd terraform/home && tofu apply

apply-cloud:
	cd terraform/cloud && tofu apply

apply-all: apply-home apply-cloud

# ── Composite targets ────────────────────────────────────────────────────────

deploy-vm: $(VENV)/bin/python3
ifndef VM
	$(error VM is required. Usage: make deploy-vm VM=docs)
endif
	$(MAKE) apply-home
	$(MAKE) apply-cloud
	cd ansible && ../$(ANSIBLE_PLAYBOOK) -i inventories/local playbooks/vms/$(VM).yml
	@$(PYTHON) scripts/log_agent_run.py deploy-vm-$(VM) done

deploy-services: $(VENV)/bin/python3
	$(MAKE) play-infra
	$(MAKE) play-pangolin
	$(MAKE) play-monitoring
	@$(PYTHON) scripts/log_agent_run.py $@ done

deploy-blueprint: $(VENV)/bin/python3
	cd ansible && ../$(ANSIBLE_PLAYBOOK) -i inventories/local -i inventories/cloud playbooks/vms/pangolin.yml --tags pangolin
	$(MAKE) play-monitoring
	@$(PYTHON) scripts/log_agent_run.py $@ done

# ── Apps ─────────────────────────────────────────────────────────────────────

HOMELAB_APPS := $(PYTHON) scripts/homelab-apps

apps-list: $(VENV)/bin/python3
	$(HOMELAB_APPS) list

apps-validate: $(VENV)/bin/python3
	$(HOMELAB_APPS) validate --strict

apps-build: $(VENV)/bin/python3
ifndef APP
	$(error APP is required. Usage: make apps-build APP=hello-world)
endif
	$(HOMELAB_APPS) build $(APP)

apps-create: $(VENV)/bin/python3
ifndef APP
	$(error APP is required. Usage: make apps-create APP=my-app)
endif
	$(HOMELAB_APPS) create $(APP)

# ── Generative scaffolding ───────────────────────────────────────────────────

add-vm: $(VENV)/bin/python3
ifndef NAME
	$(error NAME is required. Usage: make add-vm NAME=docs IP=192.168.1.110)
endif
ifndef IP
	$(error IP is required. Usage: make add-vm NAME=docs IP=192.168.1.110)
endif
	$(PYTHON) scripts/add_vm.py --name $(NAME) --ip $(IP) $(ADD_VM_ARGS)

add-service: $(VENV)/bin/python3
ifndef NAME
	$(error NAME is required. Usage: make add-service NAME=my-app DISPLAY_NAME="My App" HOST=tools PORT=8080)
endif
ifndef DISPLAY_NAME
	$(error DISPLAY_NAME is required. Usage: make add-service NAME=my-app DISPLAY_NAME="My App" HOST=tools PORT=8080)
endif
ifndef HOST
	$(error HOST is required. Usage: make add-service NAME=my-app DISPLAY_NAME="My App" HOST=tools PORT=8080)
endif
ifndef PORT
	$(error PORT is required. Usage: make add-service NAME=my-app DISPLAY_NAME="My App" HOST=tools PORT=8080)
endif
	$(PYTHON) scripts/add_service.py --name $(NAME) --display-name "$(DISPLAY_NAME)" --host $(HOST) --port $(PORT) $(ADD_SERVICE_ARGS)

rotate-secret: $(VENV)/bin/python3
ifndef KEY
	$(error KEY is required. Usage: make rotate-secret KEY=database.myapp_user_pw [VAULT=local])
endif
	$(PYTHON) scripts/rotate_secret.py --vault $(or $(VAULT),local) --key $(KEY) $(ROTATE_ARGS)

# ── Agent logging ────────────────────────────────────────────────────────────

agent-log:
	@$(PYTHON) scripts/log_agent_run.py $(TARGET) $(STATUS)

agent-decision:
	@$(PYTHON) scripts/log_agent_decision.py --decision "$(DECISION)" --reason "$(REASON)" $(if $(IMPACT),--impact "$(IMPACT)")
