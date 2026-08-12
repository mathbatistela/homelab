"""SQLite-backed task storage.

Replaces the in-memory dict that lost every task on restart/redeploy. Follows
the same pattern as apps/tiddl-manager (WAL journal, busy timeout, sqlite3.Row,
idempotent `CREATE TABLE IF NOT EXISTS` migration run at import).

The interface mirrors the dict it replaced, so the request handlers only swap
their storage calls: `all_tasks()` ~ `_tasks.values()`, `get(id)` ~ `_tasks.get`,
`exists(id)` ~ `id in _tasks`, `insert`/`update`/`delete`.

Tasks are returned as `{"id": str, "title": str, "done": bool}` — identical to
the shape the API served before.
"""

import os
import sqlite3
from pathlib import Path

DB_PATH = Path(os.environ.get("DB_PATH", "/data/adhd-board.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id       TEXT PRIMARY KEY,
    title    TEXT NOT NULL,
    done     INTEGER NOT NULL DEFAULT 0,
    position INTEGER
);
"""


def get_db() -> sqlite3.Connection:
    """Return a connection with WAL mode enabled.

    A fresh connection per call: Flask serves requests on multiple threads and
    sqlite3 connections are not shareable across them.
    """
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.row_factory = sqlite3.Row
    return conn


def migrate() -> None:
    conn = get_db()
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


def _row_to_task(row: sqlite3.Row) -> dict:
    return {"id": row["id"], "title": row["title"], "done": bool(row["done"])}


def all_tasks() -> list[dict]:
    """Every task, in creation order (what the insertion-ordered dict gave)."""
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT id, title, done FROM tasks ORDER BY position ASC"
        ).fetchall()
    finally:
        conn.close()
    return [_row_to_task(r) for r in rows]


def get(task_id: str) -> dict | None:
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT id, title, done FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
    finally:
        conn.close()
    return _row_to_task(row) if row else None


def exists(task_id: str) -> bool:
    return get(task_id) is not None


def insert(task_id: str, title: str, done: bool = False) -> dict:
    conn = get_db()
    try:
        conn.execute(
            """INSERT INTO tasks (id, title, done, position)
               VALUES (?, ?, ?, (SELECT COALESCE(MAX(position), 0) + 1 FROM tasks))""",
            (task_id, title, int(done)),
        )
        conn.commit()
    finally:
        conn.close()
    return {"id": task_id, "title": title, "done": done}


def update(task_id: str, *, title: str | None = None, done: bool | None = None) -> dict | None:
    """Apply the given fields and return the updated task (None if missing)."""
    sets = []
    params: list = []
    if title is not None:
        sets.append("title = ?")
        params.append(title)
    if done is not None:
        sets.append("done = ?")
        params.append(int(done))

    if sets:
        conn = get_db()
        try:
            params.append(task_id)
            cur = conn.execute(
                f"UPDATE tasks SET {', '.join(sets)} WHERE id = ?", params
            )
            conn.commit()
            if cur.rowcount == 0:
                return None
        finally:
            conn.close()

    return get(task_id)


def delete(task_id: str) -> bool:
    conn = get_db()
    try:
        cur = conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        conn.commit()
    finally:
        conn.close()
    return cur.rowcount > 0
