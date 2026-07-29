"""Tidal API client for listing playlist tracks."""

import json
import logging
from pathlib import Path
from typing import Any

import requests
from requests_cache import CachedSession

log = logging.getLogger(__name__)

API_URL = "https://api.tidal.com/v1"
AUTH_PATH = Path.home() / ".tiddl" / "auth.json"
COUNTRY_CODE = "BR"


class TidalClient:
    """Minimal Tidal API client using tiddl auth token."""

    def __init__(self) -> None:
        self._load_auth()
        self.session = CachedSession(
            cache_name=str(Path.home() / ".tiddl" / "api_cache"),
        )
        self.session.headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
        }

    def _load_auth(self) -> None:
        if not AUTH_PATH.exists():
            raise FileNotFoundError(
                f"Auth file not found at {AUTH_PATH}. Run 'tiddl auth login' first."
            )
        data = json.loads(AUTH_PATH.read_text())
        self.token = data["token"]
        self.user_id = data.get("user_id", "")
        self.refresh_token = data.get("refresh_token", "")
        self._client_id, self._client_secret = self._get_credentials()

    def _get_credentials(self) -> tuple[str, str]:
        """Extract client credentials from tiddl or env."""
        import base64, os
        # Same base64 encoded creds as tiddl's auth client
        default = base64.b64decode(
            "NE4zbjZRMXg5NUxMNUs3cDtvS09YZkpXMzcxY1g2eGFaMFB5aGdHTkJkTkxsQlpkNEFLS1lvdWdNamlrPQ=="
        ).decode()
        env_val = os.environ.get("TIDDL_AUTH", "")
        if env_val:
            cid, csec = env_val.split(";")
        else:
            cid, csec = default.split(";")
        return cid, csec

    def _refresh_token(self) -> bool:
        """Refresh the access token. Returns True on success."""
        try:
            resp = requests.post(
                "https://auth.tidal.com/v1/oauth2/token",
                data={
                    "client_id": self._client_id,
                    "refresh_token": self.refresh_token,
                    "grant_type": "refresh_token",
                    "scope": "r_usr+w_usr+w_sub",
                },
                auth=(self._client_id, self._client_secret),
            )
            resp.raise_for_status()
            data = resp.json()
            self.token = data["access_token"]
            self.refresh_token = data.get("refresh_token", self.refresh_token)
            self.session.headers["Authorization"] = f"Bearer {self.token}"
            # Update auth.json
            auth = json.loads(AUTH_PATH.read_text())
            auth["token"] = self.token
            auth["refresh_token"] = self.refresh_token
            AUTH_PATH.write_text(json.dumps(auth))
            return True
        except Exception as e:
            log.error("Token refresh failed: %s", e)
            return False

    def _get(self, endpoint: str, params: dict = None) -> dict:
        """Make authenticated GET request with auto-refresh."""
        params = params or {}
        params.setdefault("countryCode", COUNTRY_CODE)

        resp = self.session.get(
            f"{API_URL}/{endpoint}", params=params
        )

        if resp.status_code == 401 and self.refresh_token:
            if self._refresh_token():
                resp = self.session.get(
                    f"{API_URL}/{endpoint}", params=params
                )

        resp.raise_for_status()
        return resp.json()

    def get_playlist(self, playlist_id: str) -> dict:
        """Get playlist metadata."""
        return self._get(f"playlists/{playlist_id}")

    def get_playlist_tracks(
        self, playlist_id: str, limit: int = 100, offset: int = 0
    ) -> dict:
        """Get playlist items (tracks)."""
        return self._get(
            f"playlists/{playlist_id}/items",
            {"limit": min(limit, 100), "offset": offset},
        )

    def get_all_playlist_tracks(self, playlist_id: str) -> list[dict]:
        """Fetch all tracks from a playlist, handling pagination."""
        all_items = []
        offset = 0
        while True:
            data = self.get_playlist_tracks(playlist_id, offset=offset)
            items = data.get("items", [])
            all_items.extend(items)
            offset += data.get("limit", 100)
            if offset >= data.get("totalNumberOfItems", 0):
                break
        return all_items

    def get_track(self, track_id: str) -> dict:
        """Get single track metadata."""
        return self._get(f"tracks/{track_id}")

    def get_album(self, album_id: str) -> dict:
        """Get album metadata."""
        return self._get(f"albums/{album_id}")

    def get_album_tracks(self, album_id: str) -> list[dict]:
        """Get all tracks from an album."""
        all_items = []
        offset = 0
        while True:
            data = self._get(
                f"albums/{album_id}/items",
                {"limit": 100, "offset": offset},
            )
            items = data.get("items", [])
            all_items.extend(items)
            offset += data.get("limit", 100)
            if offset >= data.get("totalNumberOfItems", 0):
                break
        return all_items

    def get_artist(self, artist_id: str) -> dict:
        """Get artist metadata."""
        return self._get(f"artists/{artist_id}")

    def get_artist_top_tracks(self, artist_id: str) -> list[dict]:
        """Get artist top tracks."""
        data = self._get(
            f"artists/{artist_id}/tracks",
            {"limit": 50, "offset": 0},
        )
        return data.get("items", [])

    def get_artist_albums(self, artist_id: str) -> list[dict]:
        """Get all albums from an artist."""
        all_items = []
        offset = 0
        while True:
            data = self._get(
                f"artists/{artist_id}/albums",
                {"limit": 100, "offset": offset, "filter": "ALBUMS"},
            )
            items = data.get("items", [])
            all_items.extend(items)
            offset += data.get("limit", 100)
            if offset >= data.get("totalNumberOfItems", 0):
                break
        return all_items

    def extract_track_info(self, item: dict) -> dict[str, Any]:
        """Extract relevant track info from a playlist/album item.

        Handles both playlist items (item.item structure) and
        direct track objects.
        """
        track = item.get("item", item)
        artist = track.get("artist") or (
            track.get("artists", [{}])[0] if track.get("artists") else {}
        )
        return {
            "id": str(track["id"]),
            "title": track["title"],
            "artist": artist.get("name", "Unknown Artist"),
            "album_title": track.get("album", {}).get("title", ""),
            "track_number": track.get("trackNumber", 1),
            "duration": track.get("duration", 0),
            "audio_quality": track.get("audioQuality", "HIGH"),
        }
