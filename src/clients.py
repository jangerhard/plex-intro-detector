"""Tautulli and Plex API clients."""

from datetime import datetime, timedelta

import requests
from plexapi.server import PlexServer


class TautulliClient:
    """Client for Tautulli API."""

    def __init__(self, url: str, api_key: str):
        self.url = url.rstrip("/")
        self.api_key = api_key

    def _request(self, cmd: str, **params) -> dict:
        """Make API request, return response data."""
        params["apikey"] = self.api_key
        params["cmd"] = cmd
        resp = requests.get(f"{self.url}/api/v2", params=params, timeout=30)
        resp.raise_for_status()
        result = resp.json()
        if result.get("response", {}).get("result") != "success":
            raise ValueError(f"Tautulli API error: {result}")
        return result["response"]["data"]

    def get_user_id(self, username: str) -> int | None:
        """Get user ID from username (case-insensitive)."""
        users = self._request("get_users")
        for user in users:
            if user["username"].lower() == username.lower():
                return user["user_id"]
        return None

    def get_watched_shows(self, usernames: list[str], lookback_days: int) -> tuple[set[int], set[int]]:
        """Get show and episode rating keys for content watched by given users.

        Returns:
            Tuple of (show_rating_keys, episode_rating_keys)
        """
        cutoff_timestamp = (datetime.now() - timedelta(days=lookback_days)).timestamp()
        show_keys = set()
        episode_keys = set()

        for username in usernames:
            user_id = self.get_user_id(username)
            if not user_id:
                continue
            history = self._request(
                "get_history",
                user_id=user_id,
                media_type="episode",
                length=1000
            )
            for item in history.get("data", []):
                if item.get("date", 0) >= cutoff_timestamp:
                    show_keys.add(int(item["grandparent_rating_key"]))
                    episode_keys.add(int(item["rating_key"]))

        return show_keys, episode_keys


class PlexClient:
    """Client for Plex API."""

    def __init__(self, url: str, token: str):
        self.server = PlexServer(url, token)

    def get_show(self, rating_key: int):
        """Fetch show by rating key, return None if not found."""
        try:
            return self.server.fetchItem(rating_key)
        except Exception:
            return None

    def get_all_episodes(self, show) -> list:
        """Get all episodes of a show."""
        return show.episodes()

    def get_episode(self, rating_key: int):
        """Fetch episode by rating key, return None if not found."""
        try:
            return self.server.fetchItem(rating_key)
        except Exception:
            return None

    def has_intro_marker(self, episode) -> bool:
        """Check if episode has intro marker."""
        episode.reload()
        return getattr(episode, "hasIntroMarker", False)

    def has_credits_marker(self, episode) -> bool:
        """Check if episode has credits marker (indicates analyzer already ran)."""
        markers = getattr(episode, "markers", [])
        return any(getattr(m, "type", "") == "credits" for m in markers)

    def analyze(self, episode) -> None:
        """Trigger analysis for episode (fire and forget)."""
        # Fire the analyze request with a short timeout, don't wait for completion
        url = f"{self.server._baseurl}/library/metadata/{episode.ratingKey}/analyze"
        try:
            requests.put(url, params={"X-Plex-Token": self.server._token}, timeout=2)
        except requests.exceptions.Timeout:
            pass  # Expected - we don't wait for completion
        except Exception:
            pass  # Fire and forget
