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
import ipaddress
import json
import re
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
NETWORK_JSON = ROOT / "config" / "network.json"
MAIN_TF = ROOT / "terraform" / "home" / "main.tf"
HOSTS_YML = ROOT / "ansible" / "inventories" / "local" / "hosts.yml"
PLAYBOOK_DIR = ROOT / "ansible" / "playbooks" / "vms"

# The name lands in an HCL identifier position (`local.network.local_hosts.<name>`
# and the servers-map key), a YAML key in hosts.yml, and a filename — so it must
# be a bare identifier. Validating up front is what makes the remaining string
# interpolation safe.
NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]*$")
DISK_RE = re.compile(r"^\d+[KMGT]?$")


def _fail(message: str) -> "None":
    print(f"error: {message}", file=sys.stderr)
    sys.exit(1)


def validate_name(name: str) -> str:
    if not NAME_RE.match(name):
        _fail(f"--name must match {NAME_RE.pattern} (got {name!r})")
    return name


def validate_ip(ip: str) -> str:
    try:
        ipaddress.IPv4Address(ip)
    except ValueError as exc:
        _fail(f"--ip must be a valid IPv4 address (got {ip!r}): {exc}")
    return ip


def validate_disk(disk: str) -> str:
    if not DISK_RE.match(disk):
        _fail(f"--disk must match {DISK_RE.pattern} (e.g. 16G) (got {disk!r})")
    return disk


def hcl_string(value: str) -> str:
    """Render a Python string as a quoted HCL/Terraform string literal.

    HCL string escaping is JSON-compatible for the characters that matter here,
    so json.dumps gives correct quoting and turns any embedded newline into
    `\\n` instead of letting it break out of the literal. `${` is escaped as
    `$${` so a value can never smuggle in a Terraform interpolation.
    """
    if "\x00" in value:
        _fail("value contains a NUL byte")
    return json.dumps(value).replace("${", "$${")


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

    # Find the closing brace of the servers map. `name` is a validated bare
    # identifier; every other interpolated string goes through hcl_string().
    block = f'''    {name} = {{
      vmid        = {int(vmid)}
      hostname    = {hcl_string(name)}
      cores       = {int(cores)}
      memory      = {int(memory)}
      swap        = {int(swap)}
      disk_size   = {hcl_string(disk)}
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
    # (`name` is a validated bare identifier — see validate_name).
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


class _PlaybookDumper(yaml.SafeDumper):
    """SafeDumper that indents sequences under their parent key (repo style)."""

    def increase_indent(self, flow=False, indentless=False):
        return super().increase_indent(flow, False)


def create_playbook(name: str):
    path = PLAYBOOK_DIR / f"{name}.yml"
    if path.exists():
        print(f"Playbook {path.relative_to(ROOT)} already exists")
        return

    # Serialized rather than string-templated so `name` cannot inject YAML keys.
    doc = [
        {
            "name": f"Configure {name} VM",
            "hosts": name,
            "gather_facts": True,
            "become": True,
            "roles": ["REPLACE_ME"],
        }
    ]
    content = yaml.dump(
        doc,
        Dumper=_PlaybookDumper,
        sort_keys=False,
        explicit_start=True,
        default_flow_style=False,
        allow_unicode=True,
        indent=2,
        width=4096,
    )
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

    name = validate_name(args.name)
    ip = validate_ip(args.ip)
    disk = validate_disk(args.disk)

    vmid = args.vmid
    if vmid is None:
        vmid = int(ip.split(".")[-1])

    add_to_network(name, ip)
    add_to_main_tf(name, vmid, args.cores, args.memory, args.swap, disk)
    add_to_hosts_yml(name)
    create_playbook(name)

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
