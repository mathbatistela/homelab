"""Shared validation rules for apps/<name>/app.yml manifests.

`scripts/validate_sources.py` (repo-wide consistency gate) and
`scripts/homelab-apps validate` (per-app CLI) both used to carry their own
copy of these rules, and the copies had already drifted.

The checks live here and return structured `Finding`s rather than formatted
strings: the two callers report at different severities and with different
wording, so each one maps codes to its own message. Adding a rule here changes
both callers at once; how it is *phrased* and how bad it is stays with the
caller.
"""

from dataclasses import dataclass, field
from pathlib import Path

REQUIRED_FIELDS = ["name", "description", "version", "services", "homelab"]
VALID_SERVICE_TYPES = {"frontend", "backend", "worker", "proxy"}

# Finding codes
MISSING_FIELD = "missing_field"
SERVICES_NOT_MAPPING = "services_not_mapping"
SERVICE_NOT_MAPPING = "service_not_mapping"
SERVICE_MISSING_PORT = "service_missing_port"
SERVICE_UNKNOWN_TYPE = "service_unknown_type"
HOST_NOT_IN_NETWORK = "host_not_in_network"
SERVICE_DIR_MISSING = "service_dir_missing"
SERVICE_DOCKERFILE_MISSING = "service_dockerfile_missing"
NO_DOCKERFILE = "no_dockerfile"


@dataclass(frozen=True)
class Finding:
    """One rule violation. `data` carries whatever the message needs."""

    code: str
    data: dict = field(default_factory=dict)

    def __getitem__(self, key):
        return self.data[key]


def check_app_config(cfg: dict, valid_hosts: set[str] | None = None) -> list[Finding]:
    """Validate a parsed `app:` mapping.

    `valid_hosts` is the set of hosts known to config/network.json; an empty or
    None set skips the host check (same as both callers did before).
    """
    findings: list[Finding] = []

    for name in REQUIRED_FIELDS:
        if name not in cfg:
            findings.append(Finding(MISSING_FIELD, {"field": name}))

    services = cfg.get("services", {})
    if not isinstance(services, dict) or not services:
        findings.append(Finding(SERVICES_NOT_MAPPING))
    else:
        for svc_name, svc in services.items():
            if not isinstance(svc, dict):
                findings.append(Finding(SERVICE_NOT_MAPPING, {"service": svc_name}))
                continue
            if "port" not in svc:
                findings.append(Finding(SERVICE_MISSING_PORT, {"service": svc_name}))
            # Emitted whenever a `type` key is present and not recognised —
            # the broader of the two original behaviours. validate_sources.py
            # has always ignored falsy types (`type:` with no value, `type: ""`)
            # and filters those out itself, so neither caller's behaviour moves.
            if "type" in svc and svc["type"] not in VALID_SERVICE_TYPES:
                findings.append(
                    Finding(SERVICE_UNKNOWN_TYPE, {"service": svc_name, "type": svc["type"]})
                )

    homelab = cfg.get("homelab", {})
    if isinstance(homelab, dict):
        host = homelab.get("host")
        if host and valid_hosts and host not in valid_hosts:
            findings.append(Finding(HOST_NOT_IN_NETWORK, {"host": host}))

    return findings


def check_app_layout(app_dir: Path, cfg: dict) -> list[Finding]:
    """Check that each declared service has a Dockerfile on disk.

    Only `homelab-apps validate --strict` calls this — `validate_sources.py`
    has never checked Dockerfiles, and this refactor deliberately keeps that
    difference rather than silently changing either tool's behavior.
    """
    findings: list[Finding] = []
    services_subdir = app_dir / "services"

    if services_subdir.is_dir():
        for svc_name in (cfg.get("services") or {}):
            svc_dir = services_subdir / svc_name
            if not svc_dir.is_dir():
                findings.append(Finding(SERVICE_DIR_MISSING, {"service": svc_name}))
            elif not (svc_dir / "Dockerfile").exists():
                findings.append(Finding(SERVICE_DOCKERFILE_MISSING, {"service": svc_name}))
    elif not (app_dir / "Dockerfile").exists():
        findings.append(Finding(NO_DOCKERFILE))

    return findings
