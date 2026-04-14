#!/usr/bin/env python3
"""
Lint checks specifically for AGENTS.md conventions and anti-patterns.

Checks:
  - No hardcoded 192.168.1.x IPs in terraform/ *.tf files
  - No *.tfvars, vault.auth, or *.tfstate tracked by git
  - No terraform binary references in scripts/Makefile/workflows

Exit 0 if clean, 1 if warnings, 2 if errors.
"""

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
errors: list[str] = []
warnings: list[str] = []


def check_hardcoded_ips_in_terraform():
    """Ensure terraform files reference network.json instead of hardcoding IPs."""
    subnet_re = re.compile(r"192\.168\.1\.\d{1,3}")
    for fpath in (ROOT / "terraform").rglob("*.tf"):
        for i, line in enumerate(fpath.read_text().splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("#") or stripped.startswith("//"):
                continue
            if "network.json" in line:
                continue
            if subnet_re.search(line):
                errors.append(
                    f"{fpath.relative_to(ROOT)}:{i}: hardcoded IP: {stripped}"
                )


def check_gitignored_files_tracked():
    """Ensure sensitive files are not tracked by git."""
    patterns = ["*.tfvars", "vault.auth", "*.tfstate", "*.tfstate.*"]
    for pat in patterns:
        result = subprocess.run(
            ["git", "ls-files", pat],
            capture_output=True,
            text=True,
            cwd=ROOT,
        )
        if result.stdout.strip():
            errors.append(
                f"Git-tracked sensitive file(s) matching '{pat}': {result.stdout.strip()}"
            )


def check_terraform_binary_references():
    """Warn if 'terraform ' appears in automation files (prefer 'tofu')."""
    # Only check Makefile and CI workflows; Python scripts may legitimately
    # mention "Terraform" in docstrings and error messages.
    check_paths = (
        [ROOT / "Makefile"]
        + list((ROOT / ".github" / "workflows").glob("*.yml"))
    )
    for fpath in check_paths:
        for i, line in enumerate(fpath.read_text().splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("#") or stripped.startswith("//"):
                continue
            low = stripped.lower()
            # Look for literal 'terraform ' command usage, excluding tofu/opentofu/hashicorp
            if "terraform " in low and "opentofu" not in low and "tofu" not in low and "hashicorp" not in low:
                # Also exclude references to terraform/ directory
                if not stripped.startswith("terraform/") and "../terraform/" not in stripped:
                    warnings.append(
                        f"{fpath.relative_to(ROOT)}:{i}: possible 'terraform' binary reference: {stripped}"
                    )


def main() -> int:
    print("Running agent convention lint...")
    check_hardcoded_ips_in_terraform()
    check_gitignored_files_tracked()
    check_terraform_binary_references()

    if warnings:
        print(f"\n⚠ {len(warnings)} warning(s):")
        for w in warnings:
            print(f"   {w}")

    if errors:
        print(f"\n✗ {len(errors)} error(s):")
        for e in errors:
            print(f"   {e}")

    if errors:
        return 2
    if warnings:
        return 1

    print("✓ Agent conventions OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
