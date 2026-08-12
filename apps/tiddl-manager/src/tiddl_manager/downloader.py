"""Track downloading via tiddl CLI."""

import logging
import re
import subprocess
from pathlib import Path

log = logging.getLogger(__name__)

DOWNLOAD_BASE = Path("/downloads")
QUALITY = "max"

# User folder names are single path segments: letters, digits, dot, dash,
# underscore. Anything else (separators, "..", NUL, whitespace) is refused.
_USER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


class InvalidUser(ValueError):
    """Raised when a user string cannot be used as a download folder name."""


def user_download_path(user: str) -> Path:
    """Resolve the download folder for `user`, refusing anything that escapes.

    `user` reaches here from `--user` / the subscriptions table, so a value like
    "../../etc" would otherwise write outside DOWNLOAD_BASE.
    """
    if not user or not _USER_RE.match(user) or user in (".", ".."):
        raise InvalidUser(f"invalid user folder name: {user!r}")

    candidate = (DOWNLOAD_BASE / user).resolve(strict=False)
    base = DOWNLOAD_BASE.resolve(strict=False)
    if candidate != base and base not in candidate.parents:
        raise InvalidUser(f"user folder escapes {base}: {user!r}")

    return candidate


def download_track(track_id: str, user: str) -> tuple[bool, str]:
    """Download a single track via tiddl CLI.

    Returns (success, file_path_hint).
    """
    try:
        output_path = user_download_path(user)
    except InvalidUser as exc:
        log.error("Refusing download: %s", exc)
        return False, str(exc)

    cmd = [
        "tiddl",
        "download",
        "--rewrite-metadata",
        "--path", str(output_path),
        "--track-quality", QUALITY,
        "--output", "{album.artist}/{album.title}/{item.number:02d}. {item.title}",
        "url",
        f"track/{track_id}",
    ]

    log.info("Downloading track %s for user %s", track_id, user)
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            log.error("tiddl failed: %s", result.stderr[-500:])
            return False, result.stderr[-200:]
        return True, result.stdout
    except subprocess.TimeoutExpired:
        log.error("Download timed out for track %s", track_id)
        return False, "timeout"
    except FileNotFoundError:
        log.error("tiddl CLI not found in PATH")
        return False, "tiddl not found"


def download_playlist(playlist_id: str, user: str) -> tuple[bool, str]:
    """Download entire playlist via tiddl CLI (one-shot, not tracked).

    Returns (success, stdout/error).
    """
    try:
        output_path = user_download_path(user)
    except InvalidUser as exc:
        log.error("Refusing download: %s", exc)
        return False, str(exc)

    cmd = [
        "tiddl",
        "download",
        "--rewrite-metadata",
        "--path", str(output_path),
        "--track-quality", QUALITY,
        "--output", "{album.artist}/{album.title}/{item.number:02d}. {item.title}",
        "--threads-count", "4",
        "url",
        f"playlist/{playlist_id}",
    ]

    log.info("Downloading playlist %s for user %s", playlist_id, user)
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
        if result.returncode != 0:
            log.error("tiddl failed: %s", result.stderr[-500:])
            return False, result.stderr[-200:]
        return True, result.stdout
    except subprocess.TimeoutExpired:
        log.error("Download timed out for playlist %s", playlist_id)
        return False, "timeout"
    except FileNotFoundError:
        log.error("tiddl CLI not found")
        return False, "tiddl not found"
