"""Track downloading via tiddl CLI."""

import logging
import subprocess
from pathlib import Path

log = logging.getLogger(__name__)

DOWNLOAD_BASE = Path("/downloads")
QUALITY = "max"


def download_track(track_id: str, user: str) -> tuple[bool, str]:
    """Download a single track via tiddl CLI.

    Returns (success, file_path_hint).
    """
    output_path = DOWNLOAD_BASE / user

    cmd = [
        "tiddl",
        "download",
        "url",
        f"track/{track_id}",
        "--path", str(output_path),
        "--track-quality", QUALITY,
        "--output", "{album.artist}/{album.title}/{item.number:02d}. {item.title}",
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
    output_path = DOWNLOAD_BASE / user

    cmd = [
        "tiddl",
        "download",
        "url",
        f"playlist/{playlist_id}",
        "--path", str(output_path),
        "--track-quality", QUALITY,
        "--output", "{album.artist}/{album.title}/{item.number:02d}. {item.title}",
        "--threads-count", "4",
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
