#!/usr/bin/env python3
"""
Scaffold a new VM into the homelab repo.

Usage:
  python scripts/add_vm.py --name docs --ip 192.168.1.110 [options]
  make add-vm NAME=docs IP=192.168.1.110

This will:
  1. Add the host to config/network.json
  2. Add the server block to terraform/home/main.tf
  3. Add the host to ansible/inventories/local/hosts.yml (proxmox group)
  4. Create ansible/playbooks/vms/<name>.yml skeleton
  5. Run make check
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NETWORK_JSON = ROOT / "config" / "network.json"
MAIN_TF = ROOT / "terraform" / "home" / "main.tf"
HOSTS_YML = ROOT / "ansible" / "inventories" / "local" / "hosts.yml"
PLAYBOOK_DIR = ROOT / "ansible" / "playbooks" / "vms"


def load_network() -> dict:
    with open(NETWORK_JSON) as f:
        return json.load(f)


def save_network(network: dict):
    with open(NETWORK_JSON, "w") as f:
        json.dump(network, f, indent=2)
        f.write("\n")


def add_to_network(name: str, ip: str):
    network = load_network()
    if name in network.get("local_hosts", {}):
        print(f"Host '{name}' already exists in network.json ({network['local_hosts'][name]})")
        return
    network["local_hosts"][name] = ip
    save_network(network)
    print(f"Added {name}={ip} to config/network.json")


def add_to_main_tf(name: str, vmid: int, cores: int, memory: int, swap: int, disk: str):
    content = MAIN_TF.read_text()
    if f'    {name} = {{' in content:
        print(f"Server '{name}' already exists in terraform/home/main.tf")
        return

    # Find the closing brace of the servers map
    block = f'''    {name} = {{
      vmid        = {vmid}
      hostname    = "{name}"
      cores       = {cores}
      memory      = {memory}
      swap        = {swap}
      disk_size   = "{disk}"
      ip          = "${{local.network.local_hosts.{name}}}${{local.network.cidr}}"
      nameserver  = null
      mountpoints = []
    }}
'''

    # Insert before the final closing brace of servers map
    # Look for the last "  }" before "}"
    match = re.search(r'(\n  })\n}', content)
    if not match:
        print("Could not find local.servers closing brace in main.tf")
        sys.exit(1)

    insert_pos = match.start(1)
    new_content = content[:insert_pos] + "\n" + block + content[insert_pos:]
    MAIN_TF.write_text(new_content)
    print(f"Added server block for '{name}' to terraform/home/main.tf")


def add_to_hosts_yml(name: str):
    content = HOSTS_YML.read_text()
    if f"{name}: {{}}" in content:
        print(f"Host '{name}' already exists in hosts.yml")
        return

    # Find the proxmox hosts block using regex and insert alphabetically
    import re

    # Match the proxmox hosts block
    pattern = re.compile(
        r'''(    proxmox:\n(?:      .*\n|\n)*?      hosts:\n)((?:        .*\n)*?)(\n|    unmanaged:)''',
        re.MULTILINE,
    )

    def replacer(match):
        hosts_block = match.group(2)
        terminator = match.group(3)
        hosts_lines = [l for l in hosts_block.splitlines() if l.strip()]
        hosts_lines.append(f"        {name}: {{}}")
        # Sort to keep alphabetical order
        hosts_lines.sort()
        new_hosts = "\n".join(hosts_lines) + "\n"
        return match.group(1) + new_hosts + terminator

    new_content, count = pattern.subn(replacer, content)
    if count == 0:
        print("Could not find proxmox hosts block in hosts.yml")
        sys.exit(1)

    HOSTS_YML.write_text(new_content)
    print(f"Added '{name}' to ansible/inventories/local/hosts.yml")


def create_playbook(name: str):
    path = PLAYBOOK_DIR / f"{name}.yml"
    if path.exists():
        print(f"Playbook {path.relative_to(ROOT)} already exists")
        return

    content = f"""---
- name: "Configure {name} VM"
  hosts: {name}
  gather_facts: true
  become: true
  roles:
    - REPLACE_ME
"""
    path.write_text(content)
    print(f"Created playbook {path.relative_to(ROOT)}")


def run_check():
    print("\nRunning make check...")
    result = subprocess.run(["make", "check"], cwd=ROOT)
    if result.returncode != 0:
        print("\n⚠ make check failed. Please review the errors above.")
        sys.exit(1)
    print("✓ make check passed")


def main() -> int:
    parser = argparse.ArgumentParser(description="Scaffold a new VM")
    parser.add_argument("--name", required=True, help="VM hostname")
    parser.add_argument("--ip", required=True, help="Static IP, e.g. 192.168.1.110")
    parser.add_argument("--vmid", type=int, help="Proxmox VMID (default: last octet of IP)")
    parser.add_argument("--cores", type=int, default=2, help="CPU cores (default: 2)")
    parser.add_argument("--memory", type=int, default=4096, help="Memory in MB (default: 4096)")
    parser.add_argument("--swap", type=int, default=512, help="Swap in MB (default: 512)")
    parser.add_argument("--disk", default="16G", help="Disk size (default: 16G)")
    parser.add_argument("--skip-check", action="store_true", help="Skip running make check")
    args = parser.parse_args()

    vmid = args.vmid
    if vmid is None:
        vmid = int(args.ip.split(".")[-1])

    add_to_network(args.name, args.ip)
    add_to_main_tf(args.name, vmid, args.cores, args.memory, args.swap, args.disk)
    add_to_hosts_yml(args.name)
    create_playbook(args.name)

    if not args.skip_check:
        run_check()

    print(f"\n✓ VM '{args.name}' scaffolded successfully.")
    print("Next steps:")
    print(f"  1. Edit ansible/playbooks/vms/{args.name}.yml and replace REPLACE_ME with real roles")
    print(f"  2. Run: make plan-home")
    print(f"  3. Run: make apply-home")
    print(f"  4. Run: make play-{args.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
