#!/usr/bin/env python3
"""
Standalone network alignment check.
Ensures config/network.json and ansible/inventories/local/hosts.yml stay in sync.

Exit 0 if aligned, 1 if warnings, 2 if errors.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_network() -> dict:
    with open(ROOT / "config" / "network.json") as f:
        return json.load(f)


def load_ansible_hosts() -> set[str]:
    try:
        import yaml
    except ImportError as exc:
        print("PyYAML is required for check_network.py")
        raise SystemExit(2) from exc

    path = ROOT / "ansible" / "inventories" / "local" / "hosts.yml"
    with open(path) as f:
        for doc in yaml.safe_load_all(f):
            if doc is not None:
                inventory = doc
                break
        else:
            inventory = {}

    hosts: set[str] = set()

    def collect(node: dict):
        if not isinstance(node, dict):
            return
        if "hosts" in node and isinstance(node["hosts"], dict):
            hosts.update(node["hosts"].keys())
        for v in node.values():
            if isinstance(v, dict):
                collect(v)

    collect(inventory)
    hosts.discard("localhost")
    return hosts


def main() -> int:
    network = load_network()
    ansible_hosts = load_ansible_hosts()
    local_hosts = set(network.get("local_hosts", {}).keys())
    remote_hosts = set(network.get("remote_hosts", {}).keys())
    all_network_hosts = local_hosts | remote_hosts

    errors: list[str] = []
    warnings: list[str] = []

    # Local hosts in network.json should be in ansible inventory
    for host in sorted(local_hosts):
        if host not in ansible_hosts:
            warnings.append(
                f"network.json local_host '{host}' missing in ansible hosts.yml"
            )

    # Ansible hosts should exist in network.json (so vars plugin sets ansible_host)
    for host in sorted(ansible_hosts):
        if host not in all_network_hosts:
            errors.append(f"ansible host '{host}' not found in network.json")

    if warnings:
        print(f"\n⚠ {len(warnings)} warning(s):")
        for w in warnings:
            print(f"   {w}")

    if errors:
        print(f"\n✗ {len(errors)} error(s):")
        for e in errors:
            print(f"   {e}")

    if not errors and not warnings:
        print("✓ Network config aligned.")
        return 0

    return 2 if errors else 1


if __name__ == "__main__":
    sys.exit(main())
