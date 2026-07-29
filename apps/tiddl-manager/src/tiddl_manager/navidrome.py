"""Navidrome API client for library scanning (via Subsonic API)."""

import hashlib
import logging
import os
import random
import string

import requests

# Suppress InsecureRequestWarning for internal HTTPS
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

log = logging.getLogger(__name__)

NAVIDROME_URL = os.environ.get(
    "NAVIDROME_URL", "https://music.local.batistela.tech"
)
NAVIDROME_USER = os.environ.get("NAVIDROME_USER", "mbatistela")
NAVIDROME_PASSWORD = os.environ.get("NAVIDROME_PASSWORD", "")


def _auth_params() -> dict:
    """Generate Subsonic auth params (token-based)."""
    salt = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
    token = hashlib.md5(
        (NAVIDROME_PASSWORD + salt).encode()
    ).hexdigest()
    return {
        "u": NAVIDROME_USER,
        "t": token,
        "s": salt,
        "v": "1.16.1",
        "c": "tiddl-manager",
        "f": "json",
    }


def trigger_scan() -> dict:
    """Trigger a Navidrome library scan via Subsonic API."""
    if not NAVIDROME_PASSWORD:
        return {"status": "skipped", "reason": "NAVIDROME_PASSWORD not set"}

    params = _auth_params()
    try:
        resp = requests.get(
            f"{NAVIDROME_URL}/rest/startScan",
            params=params,
            verify=False,
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        scan_status = data.get("subsonic-response", {}).get("scanStatus", {})
        return {
            "status": "triggered",
            "scanning": scan_status.get("scanning", False),
            "count": scan_status.get("count", 0),
        }
    except Exception as e:
        log.error("Navidrome scan failed: %s", e)
        return {"status": "failed", "error": str(e)}
