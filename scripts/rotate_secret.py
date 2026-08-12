#!/usr/bin/env python3
"""
Rotate a secret in an Ansible vault file safely.

Usage:
  python scripts/rotate_secret.py --vault local --key database.myapp_user_pw
  make rotate-secret VAULT=local KEY=database.myapp_user_pw

This will:
  1. Prompt for the new secret value
  2. Decrypt the vault, update the key, and re-encrypt
  3. Validate the vault is readable
  4. Optionally run dry-run on affected playbooks

The value is never accepted as a command-line argument (it would leak through
shell history and `ps`). Use the interactive prompt, or `--value-stdin` for
non-interactive callers that can pipe the secret in.
"""

import argparse
import getpass
import json
import subprocess
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover - dependency is installed by `make bootstrap`
    print("PyYAML is required. Run: make bootstrap")
    sys.exit(1)

ROOT = Path(__file__).resolve().parent.parent
VAULT_AUTH = ROOT / "ansible" / "vault.auth"

VAULT_FILES = {
    "local": ROOT / "ansible" / "inventories" / "local" / "group_vars" / "all" / "vault.yml",
    "cloud": ROOT / "ansible" / "inventories" / "cloud" / "group_vars" / "all" / "vault.yml",
}


class KeyNotFound(Exception):
    """Raised when the dot-notation key path does not resolve to a scalar."""


def view_vault(path: Path) -> str:
    result = subprocess.run(
        ["ansible-vault", "view", str(path), "--vault-password-file", str(VAULT_AUTH)],
        capture_output=True,
        text=True,
        cwd=ROOT / "ansible",
    )
    if result.returncode != 0:
        print(f"Failed to decrypt vault: {result.stderr}")
        sys.exit(1)
    return result.stdout


def _find_scalar_node(content: str, parts: list[str]) -> yaml.ScalarNode:
    """Resolve a dot-notation key path to its scalar value node.

    Uses the real YAML structure (yaml.compose gives nodes carrying source
    offsets) instead of matching on leaf name + indentation, so two vault
    groups that happen to share a leaf name at the same depth can never be
    confused for one another.
    """
    node = yaml.compose(content)
    if node is None:
        raise KeyNotFound("vault is empty")

    for depth, part in enumerate(parts):
        if not isinstance(node, yaml.MappingNode):
            path_so_far = ".".join(parts[:depth]) or "<root>"
            raise KeyNotFound(f"'{path_so_far}' is not a mapping")

        for key_node, value_node in node.value:
            if isinstance(key_node, yaml.ScalarNode) and key_node.value == part:
                node = value_node
                break
        else:
            raise KeyNotFound(f"'{'.'.join(parts[:depth + 1])}' not found")

    if not isinstance(node, yaml.ScalarNode):
        raise KeyNotFound(f"'{'.'.join(parts)}' is not a scalar value")

    return node


def _top_level_keys(content: str) -> list[str]:
    try:
        node = yaml.compose(content)
    except yaml.YAMLError:
        return []
    if not isinstance(node, yaml.MappingNode):
        return []
    return [k.value for k, _ in node.value if isinstance(k, yaml.ScalarNode)]


def replace_key_in_yaml(content: str, key: str, new_value: str) -> str:
    """Return `content` with exactly the scalar at `key` replaced.

    Only the bytes spanned by that one value node are rewritten, so comments,
    ordering, and every other key survive untouched.
    """
    node = _find_scalar_node(content, key.split("."))

    # json.dumps produces a double-quoted YAML scalar with correct escaping, and
    # keeps values like `yes`, `null` or `01234` as strings.
    safe_value = json.dumps(new_value)

    start = node.start_mark.index
    end = node.end_mark.index
    return content[:start] + safe_value + content[end:]


def edit_vault(path: Path, key: str, new_value: str):
    """Decrypt, replace key, encrypt back."""
    content = view_vault(path)

    try:
        new_content = replace_key_in_yaml(content, key, new_value)
    except KeyNotFound as exc:
        print(f"Key '{key}' not found in vault ({exc}). Existing top-level keys:")
        for top_key in _top_level_keys(content):
            print(f"  {top_key}")
        sys.exit(1)
    except yaml.YAMLError as exc:
        print(f"Vault contents are not valid YAML: {exc}")
        sys.exit(1)

    # Re-parse to be sure the edit produced a loadable document with the value
    # we intended, before anything is written back to disk.
    try:
        reloaded = yaml.safe_load(new_content)
    except yaml.YAMLError as exc:
        print(f"Refusing to write: edited vault is not valid YAML: {exc}")
        sys.exit(1)

    probe = reloaded
    for part in key.split("."):
        probe = probe[part]
    if probe != new_value:
        print("Refusing to write: edited vault did not round-trip the new value.")
        sys.exit(1)

    # Encrypt back
    proc = subprocess.Popen(
        ["ansible-vault", "encrypt", "--vault-password-file", str(VAULT_AUTH), "-"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=ROOT / "ansible",
    )
    stdout, stderr = proc.communicate(input=new_content)
    if proc.returncode != 0:
        print(f"Failed to encrypt vault: {stderr}")
        sys.exit(1)

    path.write_text(stdout)
    print(f"Updated vault key '{key}'")


def validate_vault(path: Path):
    result = subprocess.run(
        ["ansible-vault", "view", str(path), "--vault-password-file", str(VAULT_AUTH)],
        capture_output=True,
        cwd=ROOT / "ansible",
    )
    if result.returncode != 0:
        print("Vault validation failed after edit!")
        sys.exit(1)
    print("✓ Vault is readable after edit")


def main() -> int:
    parser = argparse.ArgumentParser(description="Rotate an Ansible vault secret")
    parser.add_argument("--vault", choices=["local", "cloud"], default="local", help="Which vault to edit")
    parser.add_argument("--key", required=True, help="Dot-notation key path, e.g. database.myapp_user_pw")
    parser.add_argument(
        "--value-stdin",
        action="store_true",
        help="Read the new value from stdin instead of prompting (for non-interactive callers)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Run make dry-run on all playbooks after rotation")
    args = parser.parse_args()

    path = VAULT_FILES[args.vault]
    if not path.exists():
        print(f"Vault file not found: {path}")
        sys.exit(1)
    if not VAULT_AUTH.exists():
        print(f"Vault password file missing: {VAULT_AUTH}")
        sys.exit(1)

    if args.value_stdin:
        new_value = sys.stdin.readline().rstrip("\n")
    else:
        new_value = getpass.getpass(f"New value for {args.key}: ")
        confirm = getpass.getpass("Confirm: ")
        if new_value != confirm:
            print("Values do not match. Aborting.")
            sys.exit(1)

    if not new_value:
        print("Empty value provided. Aborting.")
        sys.exit(1)

    edit_vault(path, args.key, new_value)
    validate_vault(path)

    if args.dry_run:
        print("\nRunning dry-run across all playbooks...")
        result = subprocess.run(
            ["make", "dry-run-infra", "dry-run-database", "dry-run-media", "dry-run-tools", "dry-run-monitoring"],
            cwd=ROOT,
        )
        if result.returncode != 0:
            print("\n⚠ One or more dry-runs failed. Investigate before applying.")
            return 1

    print("\n✓ Secret rotation complete.")
    print("Next steps:")
    print("  1. Run: make play-<host>   # on any host that consumes this secret")
    return 0


if __name__ == "__main__":
    sys.exit(main())
