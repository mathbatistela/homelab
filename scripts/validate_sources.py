#!/usr/bin/env python3
"""
Validate consistency across the homelab sources of truth:
  - config/network.json        (IP assignments)
  - terraform/home/main.tf     (Proxmox LXC server map)
  - ansible/inventories/local/hosts.yml  (Ansible inventory)
  - config/services/**/*.yml   (service manifests)
  - config/fragments/          (Traefik & Pangolin fragments)

Options:
  --ping      Check reachability of all hosts in network.json
  --pangolin  Check Pangolin resource drift against manifests/fragments

Exit 0 if everything is consistent, 1 if there are warnings, 2 if errors.
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

errors: list[str] = []
warnings: list[str] = []


def load_network_json() -> dict:
    path = ROOT / "config" / "network.json"
    with open(path) as f:
        return json.load(f)


def parse_terraform_servers() -> set[str]:
    """Extract server keys from local.servers block in main.tf."""
    path = ROOT / "terraform" / "home" / "main.tf"
    content = path.read_text()
    keys = set()
    in_servers = False
    brace_depth = 0
    for line in content.splitlines():
        if "servers = {" in line:
            in_servers = True
            brace_depth = 1
            continue
        if in_servers:
            brace_depth += line.count("{") - line.count("}")
            if brace_depth <= 0:
                break
            if brace_depth == 2 and "= {" in line:
                match = re.match(r"\s+([\w-]+)\s*=\s*\{", line)
                if match:
                    keys.add(match.group(1))
    return keys


def parse_ansible_hosts() -> set[str]:
    """Extract all host names from hosts.yml (excluding localhost)."""
    try:
        import yaml
    except ImportError:
        return _parse_hosts_regex()

    path = ROOT / "ansible" / "inventories" / "local" / "hosts.yml"
    with open(path) as f:
        inventory = yaml.safe_load(f)

    hosts = set()
    _collect_hosts(inventory, hosts)
    hosts.discard("localhost")
    return hosts


def _collect_hosts(node: dict, hosts: set[str]):
    """Recursively collect host names from an Ansible inventory dict."""
    if not isinstance(node, dict):
        return
    if "hosts" in node and isinstance(node["hosts"], dict):
        hosts.update(node["hosts"].keys())
    if "children" in node and isinstance(node["children"], dict):
        for child in node["children"].values():
            _collect_hosts(child, hosts)
    for key, value in node.items():
        if key not in ("hosts", "children", "vars") and isinstance(value, dict):
            _collect_hosts(value, hosts)


def _parse_hosts_regex() -> set[str]:
    """Fallback host parser using regex."""
    path = ROOT / "ansible" / "inventories" / "local" / "hosts.yml"
    content = path.read_text()
    hosts = set()
    in_hosts = False
    for line in content.splitlines():
        stripped = line.strip()
        if stripped == "hosts:":
            in_hosts = True
            continue
        if in_hosts:
            if not line.startswith(" ") and not line.startswith("\t"):
                in_hosts = False
                continue
            match = re.match(r"\s+(\w[\w-]*):", stripped)
            if match:
                hosts.add(match.group(1))
    hosts.discard("localhost")
    return hosts


def parse_service_manifests() -> list[dict]:
    """Load all service manifests."""
    try:
        import yaml
    except ImportError:
        return []

    manifests = []
    services_dir = ROOT / "config" / "services"
    for path in services_dir.rglob("*.yml"):
        with open(path) as f:
            data = yaml.safe_load(f)
        if data and "service_manifest" in data:
            manifests.append(
                {"path": str(path.relative_to(ROOT)), **data["service_manifest"]}
            )
    return manifests


def check_fragment_references(manifests: list[dict]):
    """Check that fragment references in manifests have corresponding files."""
    traefik_fragments = {
        p.stem for p in (ROOT / "config" / "fragments" / "traefik").glob("*.yml")
    }
    pangolin_fragments = {
        p.stem for p in (ROOT / "config" / "fragments" / "pangolin").glob("*.yml")
    }

    for m in manifests:
        name = m["name"]
        path = m["path"]

        for scope in ("local", "public"):
            exposure = m.get("exposure", {}).get(scope, {})
            if exposure.get("mode") == "fragment":
                fragment = exposure.get("fragment")
                if not fragment:
                    errors.append(
                        f"{path}: {name} has {scope} mode=fragment but no fragment name"
                    )
                    continue

                if scope == "local" and fragment not in traefik_fragments:
                    warnings.append(
                        f"{path}: {name} references Traefik fragment '{fragment}' "
                        f"but config/fragments/traefik/{fragment}.yml does not exist"
                    )
                if scope == "public" and fragment not in pangolin_fragments:
                    warnings.append(
                        f"{path}: {name} references Pangolin fragment '{fragment}' "
                        f"but config/fragments/pangolin/{fragment}.yml does not exist"
                    )


# ── Reachability checks ─────────────────────────────────────────────────────


def check_reachability(network: dict):
    """Ping each host in network.json to verify IPs are reachable."""
    local_hosts = network.get("local_hosts", {})
    print("\n🔍 Checking host reachability...")
    unreachable = []
    for name, ip in sorted(local_hosts.items()):
        result = subprocess.run(
            ["ping", "-c", "1", "-W", "2", ip],
            capture_output=True,
        )
        if result.returncode != 0:
            unreachable.append((name, ip))
            print(f"   ✗ {name:15s} ({ip}) — unreachable")
        else:
            print(f"   ✓ {name:15s} ({ip})")

    for name, ip in unreachable:
        warnings.append(f"Host '{name}' ({ip}) is not reachable — possible IP drift")


# ── Pangolin drift detection ────────────────────────────────────────────────


def check_pangolin_drift(manifests: list[dict]):
    """Compare live Pangolin resources against manifests + fragments."""
    import urllib.request
    import ssl

    try:
        import yaml
    except ImportError:
        warnings.append("PyYAML not available — skipping Pangolin drift check")
        return

    # Load Pangolin credentials from cloud vault isn't possible without Ansible.
    # Use the API key from the vault file if decrypted, or try env var.
    import os

    api_key = os.environ.get("PANGOLIN_API_KEY")
    if not api_key:
        # Try to extract from ansible-vault view (requires vault.auth)
        vault_path = ROOT / "ansible" / "inventories" / "cloud" / "group_vars" / "all" / "vault.yml"
        vault_auth = ROOT / "ansible" / "vault.auth"
        if vault_path.exists() and vault_auth.exists():
            try:
                result = subprocess.run(
                    ["ansible-vault", "view", str(vault_path), "--vault-password-file", str(vault_auth)],
                    capture_output=True,
                    text=True,
                    cwd=ROOT / "ansible",
                )
                if result.returncode == 0:
                    for line in result.stdout.splitlines():
                        if line.startswith("pangolin_api_key:"):
                            api_key = line.split(":", 1)[1].strip().strip('"').strip("'")
                            break
            except FileNotFoundError:
                pass

    if not api_key:
        warnings.append(
            "Cannot check Pangolin drift — no API key "
            "(set PANGOLIN_API_KEY or ensure ansible vault.auth exists)"
        )
        return

    print("\n🔍 Checking Pangolin resource drift...")

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    api_url = "https://pangolin-api.batistela.tech"
    org_id = "batistela-tech"

    try:
        req = urllib.request.Request(f"{api_url}/v1/org/{org_id}/resources")
        req.add_header("Authorization", f"Bearer {api_key}")
        resp = urllib.request.urlopen(req, context=ctx, timeout=15)
        live_data = json.loads(resp.read())["data"]["resources"]
    except Exception as e:
        warnings.append(f"Cannot reach Pangolin API: {e}")
        return

    live_domains = {}
    for r in live_data:
        domain = r.get("fullDomain") or f"tcp:{r.get('proxyPort')}"
        live_domains[domain] = r["name"]

    # Build expected domains from manifests (generated) + fragments
    expected_domains = {}

    base_domain = "batistela.tech"

    for m in manifests:
        pub = m.get("exposure", {}).get("public", {})
        if pub.get("enabled") and pub.get("mode") == "generated":
            domain = f"{pub['subdomain']}.{base_domain}"
            expected_domains[domain] = m.get("display_name", m["name"])

    # Load pangolin fragments
    fragments_dir = ROOT / "config" / "fragments" / "pangolin"
    for fpath in fragments_dir.glob("*.yml"):
        with open(fpath) as f:
            data = yaml.safe_load(f)
        resources = data.get("pangolin_fragment_resources", {})
        for key, val in resources.items():
            raw_domain = val.get("full-domain", "")
            # Resolve Jinja2 template references
            domain = raw_domain.replace("{{ pangolin_base_domain }}", base_domain)
            if not domain and val.get("proxy-port"):
                domain = f"tcp:{val['proxy-port']}"
            if domain:
                expected_domains[domain] = val.get("name", key)

    missing = {d: n for d, n in expected_domains.items() if d not in live_domains}
    extra = {d: n for d, n in live_domains.items() if d not in expected_domains}

    if missing:
        for domain, name in sorted(missing.items()):
            warnings.append(f"Pangolin missing resource: {name} ({domain})")
            print(f"   ✗ missing: {name:20s} -> {domain}")

    if extra:
        for domain, name in sorted(extra.items()):
            warnings.append(f"Pangolin extra resource not in IaC: {name} ({domain})")
            print(f"   ? extra:   {name:20s} -> {domain}")

    if not missing and not extra:
        print(f"   ✓ All {len(live_domains)} Pangolin resources match IaC")


# ── Main ─────────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="Validate homelab sources of truth")
    parser.add_argument(
        "--ping", action="store_true", help="Check reachability of hosts in network.json"
    )
    parser.add_argument(
        "--pangolin", action="store_true", help="Check Pangolin resource drift"
    )
    args = parser.parse_args()

    network = load_network_json()
    all_network_hosts = set(network.get("local_hosts", {}).keys()) | set(
        network.get("remote_hosts", {}).keys()
    )
    local_network_hosts = set(network.get("local_hosts", {}).keys())

    terraform_servers = parse_terraform_servers()
    ansible_hosts = parse_ansible_hosts()
    manifests = parse_service_manifests()

    # 1. Terraform servers must exist in network.json
    for server in sorted(terraform_servers):
        if server not in local_network_hosts:
            errors.append(
                f"Terraform server '{server}' not found in network.json local_hosts"
            )

    # 2. network.json local_hosts should have corresponding ansible inventory entries
    for host in sorted(local_network_hosts):
        if host not in ansible_hosts:
            warnings.append(
                f"network.json host '{host}' has no entry in ansible hosts.yml"
            )

    # 3. Ansible hosts should exist in network.json (for the vars plugin to work)
    for host in sorted(ansible_hosts):
        if host not in all_network_hosts:
            errors.append(
                f"Ansible host '{host}' not found in network.json — "
                f"vars plugin won't set ansible_host"
            )

    # 4. Service manifest hosts must exist in network.json
    for m in manifests:
        host = m.get("host")
        if host and host not in all_network_hosts:
            errors.append(
                f"{m['path']}: service '{m['name']}' references host '{host}' "
                f"not found in network.json"
            )

    # 5. Fragment references
    check_fragment_references(manifests)

    # 6. Optional: reachability
    if args.ping:
        check_reachability(network)

    # 7. Optional: Pangolin drift
    if args.pangolin:
        check_pangolin_drift(manifests)

    # Report
    if warnings:
        print(f"\n⚠  {len(warnings)} warning(s):")
        for w in warnings:
            print(f"   {w}")

    if errors:
        print(f"\n✗  {len(errors)} error(s):")
        for e in errors:
            print(f"   {e}")

    if not warnings and not errors:
        print("✓  All sources of truth are consistent.")
        return 0

    print()
    if errors:
        return 2
    return 1


if __name__ == "__main__":
    sys.exit(main())
