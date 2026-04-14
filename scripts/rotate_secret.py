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
"""

import argparse
import getpass
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VAULT_AUTH = ROOT / "ansible" / "vault.auth"

VAULT_FILES = {
    "local": ROOT / "ansible" / "inventories" / "local" / "group_vars" / "all" / "vault.yml",
    "cloud": ROOT / "ansible" / "inventories" / "cloud" / "group_vars" / "all" / "vault.yml",
}


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


def edit_vault(path: Path, key: str, new_value: str):
    """Decrypt, replace key, encrypt back."""
    content = view_vault(path)

    # Build regex for the key path (supports dot-notation like database.myapp_user_pw)
    # Vault files are typically flat YAML, e.g.:
    # database:
    #   myapp_user_pw: "secret"
    # We do a simple line-based replacement within the file.
    parts = key.split(".")
    if len(parts) == 1:
        pattern = re.compile(rf"^({re.escape(parts[0])}:\s*).*$", re.MULTILINE)
    else:
        # Look for the key under its parent section
        # This is a best-effort parser for typical flat vaults
        pattern = re.compile(rf"^({'  ' * (len(parts) - 1)}{re.escape(parts[-1])}:\s*).*$", re.MULTILINE)

    if not pattern.search(content):
        print(f"Key '{key}' not found in vault. Existing top-level keys:")
        for line in content.splitlines():
            if not line.startswith(" ") and ":" in line:
                print(f"  {line.split(':')[0]}")
        sys.exit(1)

    # Quote the value if it contains special chars
    if any(c in new_value for c in ['"', "'", ":", "#", " ", "\n"]):
        safe_value = json.dumps(new_value)
    else:
        safe_value = new_value

    new_content = pattern.sub(rf"\1{safe_value}", content)

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
    parser.add_argument("--value", default=None, help="New value (if omitted, prompts securely)")
    parser.add_argument("--dry-run", action="store_true", help="Run make dry-run on all playbooks after rotation")
    args = parser.parse_args()

    path = VAULT_FILES[args.vault]
    if not path.exists():
        print(f"Vault file not found: {path}")
        sys.exit(1)
    if not VAULT_AUTH.exists():
        print(f"Vault password file missing: {VAULT_AUTH}")
        sys.exit(1)

    new_value = args.value
    if new_value is None:
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
