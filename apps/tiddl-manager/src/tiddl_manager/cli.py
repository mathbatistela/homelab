"""tiddl-manager CLI — manage Tidal playlist subscriptions."""

import logging
import re
from pathlib import Path
from typing import Optional

import typer

from .db import get_db, migrate
from .state import (
    add_subscription,
    remove_subscription,
    list_subscriptions,
    get_subscription,
)
from .sync import sync_all
from .downloader import download_track, download_playlist

app = typer.Typer(
    name="tiddl-manager",
    help="Manage Tidal playlist subscriptions and sync to Navidrome.",
    no_args_is_help=True,
)

log = logging.getLogger(__name__)


def _parse_tidal_url(url: str) -> tuple[str, str]:
    """Parse a Tidal URL or resource/id string.

    Returns (resource_type, resource_id).

    Examples:
        https://tidal.com/browse/playlist/uuid-123 → ('playlist', 'uuid-123')
        track/103805726 → ('track', '103805726')
        album/103805723 → ('album', '103805723')
    """
    # Try resource/id format first
    if "/" in url and not url.startswith("http"):
        parts = url.split("/")
        if len(parts) == 2:
            return parts[0], parts[1]

    # Try Tidal URL
    match = re.search(r"tidal\.com/(?:browse/)?(\w+)/([\w-]+)", url)
    if match:
        return match.group(1), match.group(2)

    raise typer.BadParameter(
        f"Invalid URL or resource format: {url}. "
        "Use 'track/ID', 'album/ID', 'playlist/ID', or a full Tidal URL."
    )


def _resolve_name(client, rtype: str, rid: str) -> str:
    """Resolve a friendly name for the resource."""
    from .tidal_api import TidalClient

    api = TidalClient()
    try:
        if rtype == "playlist":
            return api.get_playlist(rid).get("title", rid)
        elif rtype == "album":
            return api.get_album(rid).get("title", rid)
        elif rtype == "artist":
            return api.get_artist(rid).get("name", rid)
    except Exception:
        pass
    return rid


@app.command()
def subscribe(
    url: str = typer.Argument(..., help="Tidal URL or resource/id (e.g. playlist/uuid)"),
    user: str = typer.Option(
        ..., "--user", "-u", help="User folder: matheus, pamella, yoko, or shared"
    ),
    name: Optional[str] = typer.Option(
        None, "--name", "-n", help="Custom name (default: fetched from Tidal)"
    ),
):
    """Subscribe to a Tidal playlist, album, or artist for automatic syncing."""
    rtype, rid = _parse_tidal_url(url)

    conn = get_db()
    migrate(conn)

    if get_subscription(conn, rid):
        typer.echo(f"Already subscribed to {rtype}/{rid}")
        return

    display_name = name or _resolve_name(None, rtype, rid)
    sub = add_subscription(conn, rid, display_name, user, rtype=rtype)

    typer.echo(
        f"✓ Subscribed: [{sub['type']}] {sub['name']} → user '{sub['user']}'"
    )


@app.command()
def unsubscribe(
    id: str = typer.Argument(..., help="Subscription ID (playlist/album/artist UUID)"),
):
    """Stop following a subscription."""
    conn = get_db()
    migrate(conn)
    removed = remove_subscription(conn, id)
    if removed:
        typer.echo(f"✓ Unsubscribed: {id}")
    else:
        typer.echo(f"✗ Not found: {id}")


@app.command("list")
def list_cmd(
    user: Optional[str] = typer.Option(
        None, "--user", "-u", help="Filter by user"
    ),
):
    """List all subscriptions."""
    conn = get_db()
    migrate(conn)
    subs = list_subscriptions(conn, user=user)

    if not subs:
        typer.echo("No subscriptions found.")
        return

    typer.echo(f"{'ID':<40} {'Type':<10} {'User':<10} {'Name':<30} {'Last Sync':<20} {'Tracks':>7}")
    typer.echo("-" * 120)
    for s in subs:
        last = s.get("last_sync", "-") or "-"
        last_short = last[:19] if last != "-" else "-"
        typer.echo(
            f"{s['id']:<40} {s['type']:<10} {s['user']:<10} "
            f"{s['name'][:28]:<30} {last_short:<20} {s.get('track_count', 0):>7}"
        )


@app.command()
def sync(
    user: Optional[str] = typer.Option(
        None, "--user", "-u", help="Sync only subscriptions for this user"
    ),
):
    """Sync all subscriptions — downloads only new tracks."""
    conn = get_db()
    migrate(conn)

    typer.echo(f"Syncing{' for ' + user if user else ' all users'}...")
    results = sync_all(conn, user=user)

    if not results:
        typer.echo("Nothing to sync.")
        return

    total_new = 0
    total_skip = 0
    for r in results:
        icon = "✓" if r["status"] == "done" else "✗"
        typer.echo(
            f"  {icon} {r['subscription']} ({r['user']}): "
            f"{r['new_tracks']} new, {r['skipped']} skipped"
        )
        total_new += r["new_tracks"]
        total_skip += r["skipped"]

    typer.echo(f"\nTotal: {total_new} downloaded, {total_skip} skipped")


@app.command()
def download(
    url: str = typer.Argument(..., help="Tidal URL or resource/id"),
    user: str = typer.Option(
        ..., "--user", "-u", help="User folder: matheus, pamella, yoko, or shared"
    ),
):
    """One-shot download: track, playlist, album, or artist."""
    rtype, rid = _parse_tidal_url(url)

    if rtype == "track":
        success, msg = download_track(rid, user)
    elif rtype in ("playlist", "album", "artist"):
        # For playlists/albums/artists, use tiddl directly
        from .downloader import download_playlist
        success, msg = download_playlist(rid, user)
    else:
        typer.echo(f"Unsupported resource type: {rtype}")
        raise typer.Exit(1)

    if success:
        typer.echo(f"✓ Download complete: {rtype}/{rid}")
    else:
        typer.echo(f"✗ Download failed: {msg[-200:]}")
        raise typer.Exit(1)


@app.command()
def history(
    subscription_id: str = typer.Argument(..., help="Subscription ID"),
    limit: int = typer.Option(10, "--limit", "-n", help="Number of runs to show"),
):
    """Show sync history for a subscription."""
    conn = get_db()
    migrate(conn)

    sub = get_subscription(conn, subscription_id)
    if not sub:
        typer.echo(f"Subscription not found: {subscription_id}")
        raise typer.Exit(1)

    rows = conn.execute(
        """SELECT * FROM sync_runs
           WHERE subscription_id = ?
           ORDER BY started_at DESC
           LIMIT ?""",
        (subscription_id, limit),
    ).fetchall()

    typer.echo(f"\nSync history for '{sub['name']}' ({sub['user']}):")
    typer.echo(f"{'Date':<20} {'Status':<10} {'New':>6} {'Skipped':>8} {'Error'}")
    typer.echo("-" * 80)
    for r in rows:
        err = (r["error"] or "")[:40]
        typer.echo(
            f"{r['started_at'][:19]:<20} {r['status']:<10} "
            f"{r['new_tracks']:>6} {r['skipped']:>8} {err}"
        )
