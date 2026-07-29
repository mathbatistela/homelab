"""Sync logic: check subscriptions and download new tracks."""

import logging
import sqlite3
from datetime import datetime, timezone
from typing import Optional

from .tidal_api import TidalClient
from .downloader import download_track
from . import state

log = logging.getLogger(__name__)


def sync_subscription(
    conn: sqlite3.Connection,
    client: TidalClient,
    sub: dict,
) -> dict:
    """Sync a single subscription. Returns summary dict."""
    playlist_id = sub["id"]
    username = sub["user"]
    rtype = sub.get("type", "playlist")

    # Create sync run
    now = datetime.now(timezone.utc).isoformat()
    cur = conn.execute(
        "INSERT INTO sync_runs (subscription_id, started_at, status) VALUES (?, ?, 'running')",
        (playlist_id, now),
    )
    run_id = cur.lastrowid

    new_count = 0
    skip_count = 0
    error = None

    try:
        # Fetch all tracks from the playlist/album/artist
        if rtype == "playlist":
            items = client.get_all_playlist_tracks(playlist_id)
        elif rtype == "album":
            items = client.get_album_tracks(playlist_id)
        elif rtype == "artist":
            items = client.get_artist_top_tracks(playlist_id)
        else:
            raise ValueError(f"Unknown subscription type: {rtype}")

        log.info("Syncing '%s' (%s): %d tracks total", sub["name"], username, len(items))

        for item in items:
            track_info = client.extract_track_info(item)
            track_id = track_info["id"]

            # Check if already downloaded for this subscription
            existing = conn.execute(
                "SELECT 1 FROM downloaded_tracks WHERE id = ? AND subscription_id = ?",
                (track_id, playlist_id),
            ).fetchone()

            if existing:
                skip_count += 1
                continue

            # Download
            success, output = download_track(track_id, username)
            if success:
                conn.execute(
                    """INSERT OR IGNORE INTO downloaded_tracks
                       (id, subscription_id, title, artist, file_path)
                       VALUES (?, ?, ?, ?, ?)""",
                    (
                        track_id,
                        playlist_id,
                        track_info["title"],
                        track_info["artist"],
                        f"{username}/{track_info['artist']}/{track_info['album_title']}/{track_info['track_number']:02d}. {track_info['title']}",
                    ),
                )
                new_count += 1
            else:
                log.error("Failed to download track %s: %s", track_id, output[:200])

        # Update subscription
        state.update_last_sync(conn, playlist_id, len(items))

    except Exception as e:
        error = str(e)
        log.exception("Sync failed for %s", sub["name"])

    # Complete sync run
    finished = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """UPDATE sync_runs
           SET finished_at = ?, status = ?, new_tracks = ?, skipped = ?, error = ?
           WHERE id = ?""",
        (finished, "failed" if error else "done", new_count, skip_count, error, run_id),
    )
    conn.commit()

    return {
        "subscription": sub["name"],
        "user": username,
        "status": "failed" if error else "done",
        "new_tracks": new_count,
        "skipped": skip_count,
        "error": error,
    }


def sync_all(
    conn: sqlite3.Connection,
    user: Optional[str] = None,
) -> list[dict]:
    """Sync all subscriptions, optionally filtered by user."""
    client = TidalClient()
    subs = state.list_subscriptions(conn, user=user)

    if not subs:
        log.info("No subscriptions found%s", f" for user {user}" if user else "")
        return []

    results = []
    for sub in subs:
        result = sync_subscription(conn, client, sub)
        results.append(result)

    return results
