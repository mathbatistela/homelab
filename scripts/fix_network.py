#!/usr/bin/env python3
"""
Auto-align ansible/inventories/local/hosts.yml with config/network.json.

Ensures every local_host in network.json appears in the proxmox group of hosts.yml.
Preserves unmanaged hosts and all other groups.

Usage:
  python scripts/fix_network.py
  make fix-network
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NETWORK_JSON = ROOT / "config" / "network.json"
HOSTS_YML = ROOT / "ansible" / "inventories" / "local" / "hosts.yml"


def load_network_hosts() -> set[str]:
    with open(NETWORK_JSON) as f:
        data = json.load(f)
    return set(data.get("local_hosts", {}).keys())


def load_yaml():
    try:
        import yaml
    except ImportError as exc:
        print("PyYAML is required")
        raise SystemExit(1) from exc
    return yaml


def load_hosts_raw():
    yaml = load_yaml()
    with open(HOSTS_YML) as f:
        docs = list(yaml.safe_load_all(f))
    # Skip empty documents caused by leading --- markers
    for doc in docs:
        if doc is not None:
            return doc
    return {}


def save_hosts(doc):
    yaml = load_yaml()
    with open(HOSTS_YML, "w") as f:
        # Preserve the double-document-start marker
        f.write("---\n---\n")
        yaml.dump(doc, f, default_flow_style=False, sort_keys=False)
        f.write("\n")


def fix():
    network_hosts = load_network_hosts()
    doc = load_hosts_raw()

    if not doc:
        print("Could not parse hosts.yml")
        return 1

    proxmox_hosts = doc.get("all", {}).get("children", {}).get("proxmox", {}).get("hosts", {})
    unmanaged_hosts = doc.get("all", {}).get("children", {}).get("unmanaged", {}).get("hosts", {})

    # Determine which network hosts should be in proxmox (all except unmanaged)
    current_unmanaged = set(unmanaged_hosts.keys())
    expected_proxmox = network_hosts - current_unmanaged - {"localhost"}

    current_proxmox = set(proxmox_hosts.keys())

    added = expected_proxmox - current_proxmox
    removed = current_proxmox - expected_proxmox

    if not added and not removed:
        print("✓ hosts.yml is already aligned with network.json")
        return 0

    # Rebuild proxmox hosts preserving order where possible
    new_proxmox = {}
    for h in sorted(expected_proxmox):
        new_proxmox[h] = proxmox_hosts.get(h, {})

    doc["all"]["children"]["proxmox"]["hosts"] = new_proxmox
    save_hosts(doc)

    if added:
        print(f"Added to proxmox hosts: {', '.join(sorted(added))}")
    if removed:
        print(f"Removed from proxmox hosts: {', '.join(sorted(removed))}")

    print("\n✓ hosts.yml aligned. Run 'make syntax-check' to verify.")
    return 0


def main() -> int:
    return fix()


if __name__ == "__main__":
    sys.exit(main())
