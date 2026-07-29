"""Subscription CRUD operations."""

import sqlite3
from datetime import datetime, timezone
from typing import Optional


def add_subscription(
    conn: sqlite3.Connection,
    playlist_id: str,
    name: str,
    user: str,
    rtype: str = "playlist",
) -> dict:
    """Add a new subscription. Raises if already exists."""
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT INTO subscriptions (id, name, type, user, created_at) VALUES (?, ?, ?, ?, ?)",
        (playlist_id, name, rtype, user, now),
    )
    conn.commit()
    return {
        "id": playlist_id,
        "name": name,
        "type": rtype,
        "user": user,
        "created_at": now,
    }


def remove_subscription(conn: sqlite3.Connection, playlist_id: str) -> bool:
    """Remove a subscription. Returns True if deleted."""
    cur = conn.execute("DELETE FROM subscriptions WHERE id = ?", (playlist_id,))
    conn.commit()
    return cur.rowcount > 0


def list_subscriptions(
    conn: sqlite3.Connection, user: Optional[str] = None
) -> list[dict]:
    """List all subscriptions, optionally filtered by user."""
    if user:
        rows = conn.execute(
            "SELECT * FROM subscriptions WHERE user = ? ORDER BY created_at DESC",
            (user,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM subscriptions ORDER BY user, created_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def get_subscription(
    conn: sqlite3.Connection, playlist_id: str
) -> Optional[dict]:
    """Get a single subscription by ID."""
    row = conn.execute(
        "SELECT * FROM subscriptions WHERE id = ?", (playlist_id,)
    ).fetchone()
    return dict(row) if row else None


def update_last_sync(
    conn: sqlite3.Connection,
    playlist_id: str,
    track_count: int,
) -> None:
    """Update last_sync timestamp and track count."""
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "UPDATE subscriptions SET last_sync = ?, track_count = ? WHERE id = ?",
        (now, track_count, playlist_id),
    )
    conn.commit()
