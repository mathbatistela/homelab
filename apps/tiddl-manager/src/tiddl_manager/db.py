"""SQLite database connection and migrations."""

import sqlite3
from pathlib import Path

DB_PATH = Path.home() / ".tiddl-manager" / "tiddl-manager.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS subscriptions (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    type        TEXT NOT NULL DEFAULT 'playlist',
    user        TEXT NOT NULL,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    last_sync   TEXT,
    track_count INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS sync_runs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    subscription_id TEXT NOT NULL REFERENCES subscriptions(id),
    started_at      TEXT NOT NULL DEFAULT (datetime('now')),
    finished_at     TEXT,
    status          TEXT DEFAULT 'running',
    new_tracks      INTEGER DEFAULT 0,
    skipped         INTEGER DEFAULT 0,
    error           TEXT
);

CREATE TABLE IF NOT EXISTS downloaded_tracks (
    id              TEXT NOT NULL,
    subscription_id TEXT NOT NULL REFERENCES subscriptions(id),
    title           TEXT NOT NULL,
    artist          TEXT,
    file_path       TEXT,
    downloaded_at   TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (id, subscription_id)
);

CREATE INDEX IF NOT EXISTS idx_sync_runs_sub ON sync_runs(subscription_id);
CREATE INDEX IF NOT EXISTS idx_downloads_sub ON downloaded_tracks(subscription_id);
CREATE INDEX IF NOT EXISTS idx_subs_user ON subscriptions(user);
"""


def get_db() -> sqlite3.Connection:
    """Return connection with WAL mode and foreign keys enabled."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


def migrate(conn: sqlite3.Connection) -> None:
    """Run schema migrations."""
    conn.executescript(SCHEMA)
    conn.commit()
