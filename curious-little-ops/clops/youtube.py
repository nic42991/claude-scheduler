"""YouTube Data API v3 - upload Shorts / videos and read basic channel stats.

Setup (one time):
  1. console.cloud.google.com -> new project -> enable "YouTube Data API v3".
  2. OAuth consent screen (External, add your Google account as test user).
  3. Create OAuth client (Desktop app) -> client id + secret.
  4. Run scripts/youtube_auth.py once on your laptop; it prints a refresh token.
Store client id/secret/refresh token in secrets.

Quota: an upload costs ~1600 units of the 10,000 daily default, so max ~6 uploads/day.
"""
from __future__ import annotations

import json
from pathlib import Path

import requests

from .config import Secrets
from .http import ApiError, call

TOKEN_URL = "https://oauth2.googleapis.com/token"
UPLOAD_URL = "https://www.googleapis.com/upload/youtube/v3/videos"
API = "https://www.googleapis.com/youtube/v3"


class YouTube:
    def __init__(self, secrets: Secrets):
        self.client_id, self.client_secret, self.refresh_token = secrets.require(
            "youtube_client_id", "youtube_client_secret", "youtube_refresh_token"
        )
        self._access: str | None = None

    def _token(self) -> str:
        if self._access:
            return self._access
        r = call(
            "youtube",
            "POST",
            TOKEN_URL,
            data={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "refresh_token": self.refresh_token,
                "grant_type": "refresh_token",
            },
        )
        self._access = r["access_token"]
        return self._access

    def _h(self) -> dict:
        return {"Authorization": f"Bearer {self._token()}"}

    # ---- read ----
    def channel_stats(self) -> dict:
        r = call("youtube", "GET", f"{API}/channels", headers=self._h(), params={"part": "statistics,snippet", "mine": "true"})
        items = r.get("items") or []
        if not items:
            return {}
        s = items[0]["statistics"]
        return {
            "title": items[0]["snippet"]["title"],
            "subscribers": int(s.get("subscriberCount", 0)),
            "views": int(s.get("viewCount", 0)),
            "videos": int(s.get("videoCount", 0)),
        }

    # ---- write ----
    def upload(
        self,
        video_path: str | Path,
        *,
        title: str,
        description: str,
        tags: list[str] | None = None,
        made_for_kids: bool = True,
        privacy: str = "public",
        category_id: str = "27",  # Education
    ) -> dict:
        """Resumable upload. For a Short: vertical video <= 60s, '#Shorts' in title/description."""
        p = Path(video_path)
        meta = {
            "snippet": {
                "title": title[:100],
                "description": description[:5000],
                "tags": (tags or [])[:30],
                "categoryId": category_id,
            },
            "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": made_for_kids},
        }
        init = requests.post(
            UPLOAD_URL,
            params={"uploadType": "resumable", "part": "snippet,status"},
            headers={**self._h(), "Content-Type": "application/json; charset=UTF-8", "X-Upload-Content-Type": "video/*"},
            data=json.dumps(meta),
            timeout=60,
        )
        if init.status_code >= 400:
            raise ApiError("youtube", init.status_code, init.text)
        session_url = init.headers["Location"]
        with p.open("rb") as f:
            up = requests.put(session_url, headers={"Content-Type": "video/*"}, data=f, timeout=1800)
        if up.status_code >= 400:
            raise ApiError("youtube", up.status_code, up.text)
        return up.json()
