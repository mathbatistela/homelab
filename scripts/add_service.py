#!/usr/bin/env python3
"""
Scaffold a new service manifest.

Usage:
  python scripts/add_service.py --name my-app --display-name "My App" --host tools --port 8080 [--group tools]
  make add-service NAME=my-app DISPLAY_NAME="My App" HOST=tools PORT=8080

This will:
  1. Create config/services/<group>/<name>.yml from a template
  2. Validate it against config/services/schema.json
  3. Remind you to wire the role into the target playbook
"""

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SERVICES_DIR = ROOT / "config" / "services"
SCHEMA_PATH = ROOT / "config" / "services" / "schema.json"

# --name/--group become path components, so they must be single safe segments.
SLUG_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9._-]*$")


def _check_slug(label: str, value: str) -> str:
    """Reject values that could escape config/services/ or break the filename."""
    if not SLUG_RE.match(value):
        print(
            f"error: {label} must match {SLUG_RE.pattern} (got {value!r})",
            file=sys.stderr,
        )
        sys.exit(1)
    return value


def build_manifest(args, group: str, subdomain: str, role: str) -> dict:
    """Build the manifest document. Values go through yaml.safe_dump, never
    string interpolation, so a name/display_name containing ':' or a newline
    cannot inject extra keys."""
    if args.public:
        public = {
            "enabled": True,
            "mode": "generated",
            "subdomain": subdomain,
            "protocol": args.protocol,
        }
    else:
        public = {"enabled": False, "mode": "generated"}

    return {
        "service_manifest": {
            "name": args.name,
            "display_name": args.display_name,
            "host": args.host,
            "service": {"port": args.port, "protocol": args.protocol},
            "exposure": {
                "local": {
                    "enabled": True,
                    "mode": "generated",
                    "template": "simple-http",
                    "subdomain": subdomain,
                },
                "public": public,
            },
            "auth": {"sso": args.sso},
            "deployment": {"owner": "role", "role": role},
        }
    }


def dump_manifest(manifest: dict) -> str:
    import yaml

    return yaml.safe_dump(
        manifest,
        sort_keys=False,
        default_flow_style=False,
        allow_unicode=True,
        indent=2,
        width=4096,
    )


def validate_manifest(path: Path) -> bool:
    try:
        import jsonschema
        import yaml
    except ImportError as exc:
        print(f"Missing dependency: {exc}")
        return False

    with open(SCHEMA_PATH) as f:
        schema = json.load(f)

    with open(path) as f:
        doc = yaml.safe_load(f)

    validator = jsonschema.Draft7Validator(schema)
    errors = list(validator.iter_errors(doc))
    if errors:
        print(f"\n✗ Schema validation failed for {path.relative_to(ROOT)}:")
        for e in errors:
            print(f"   {e.message}")
        return False
    print(f"✓ Schema validation passed")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Scaffold a new service manifest")
    parser.add_argument("--name", required=True, help="Service machine name")
    parser.add_argument("--display-name", required=True, help="Human-friendly name")
    parser.add_argument("--host", required=True, help="Ansible inventory host")
    parser.add_argument("--port", type=int, required=True, help="Service port")
    parser.add_argument("--protocol", default="http", choices=["http", "https", "tcp"], help="Service protocol")
    parser.add_argument("--group", default=None, help="Directory under config/services/ (default: --host)")
    parser.add_argument("--subdomain", default=None, help="Subdomain for routing (default: --name)")
    parser.add_argument("--local", action="store_true", default=True, help="Enable local Traefik exposure")
    parser.add_argument("--public", action="store_true", default=False, help="Enable public Pangolin exposure")
    parser.add_argument("--sso", action="store_true", default=False, help="Enable SSO")
    parser.add_argument("--role", default=None, help="Ansible role name (default: --name)")
    args = parser.parse_args()

    _check_slug("--name", args.name)
    group = _check_slug("--group", args.group or args.host)
    subdomain = args.subdomain or args.name
    role = args.role or args.name.replace("-", "_")
    services_group_dir = SERVICES_DIR / group
    services_group_dir.mkdir(parents=True, exist_ok=True)

    path = services_group_dir / f"{args.name}.yml"
    if path.exists():
        print(f"Service manifest already exists: {path.relative_to(ROOT)}")
        return 1

    try:
        content = dump_manifest(build_manifest(args, group, subdomain, role))
    except ImportError as exc:
        print(f"Missing dependency: {exc}", file=sys.stderr)
        return 1

    path.write_text(content)
    print(f"Created {path.relative_to(ROOT)}")

    ok = validate_manifest(path)
    if not ok:
        return 1

    print("\nNext steps:")
    print(f"  1. Ensure the Ansible role '{role}' exists under ansible/roles/{role}/")
    print(f"  2. Add the role to ansible/playbooks/vms/{args.host}.yml")
    if args.public:
        print(f"  3. Run: make play-{args.host} && make play-infra && make play-pangolin")
    else:
        print(f"  3. Run: make play-{args.host} && make play-infra")
    return 0


if __name__ == "__main__":
    sys.exit(main())
