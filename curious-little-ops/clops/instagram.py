"""Instagram publishing via the Meta Graph API (Instagram Business account).

Setup (one time):
  1. Instagram account must be Business/Creator and linked to a Facebook Page.
  2. developers.facebook.com -> create app (type Business) -> add "Instagram Graph API".
  3. Graph API Explorer -> get a User token with scopes
       instagram_basic, instagram_content_publish, pages_show_list, pages_read_engagement, business_management
     -> exchange for a long-lived token (60 days) -> fetch the Page token.
  4. GET /me/accounts -> page id -> GET /{page-id}?fields=instagram_business_account -> ig user id
Store page token as instagram_token and the ig user id as instagram_user_id.

Media must be reachable at a PUBLIC https URL (we use the repo's raw GitHub URLs).
"""
from __future__ import annotations

import time

from .config import Secrets
from .http import ApiError, call

GRAPH = "https://graph.facebook.com/v21.0"


class Instagram:
    def __init__(self, secrets: Secrets):
        self.token, self.user_id = secrets.require("instagram_token", "instagram_user_id")

    def _p(self, extra: dict | None = None) -> dict:
        return {"access_token": self.token, **(extra or {})}

    # ---- read ----
    def account(self) -> dict:
        return call(
            "instagram",
            "GET",
            f"{GRAPH}/{self.user_id}",
            params=self._p({"fields": "username,followers_count,media_count"}),
        )

    def recent_media(self, limit: int = 10) -> list[dict]:
        r = call(
            "instagram",
            "GET",
            f"{GRAPH}/{self.user_id}/media",
            params=self._p({"fields": "id,caption,media_type,permalink,timestamp,like_count,comments_count", "limit": limit}),
        )
        return r.get("data", [])

    # ---- write ----
    def _wait_ready(self, creation_id: str, timeout_s: int = 300) -> None:
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            r = call("instagram", "GET", f"{GRAPH}/{creation_id}", params=self._p({"fields": "status_code,status"}))
            code = r.get("status_code")
            if code == "FINISHED":
                return
            if code == "ERROR":
                raise ApiError("instagram", 400, f"container error: {r}")
            time.sleep(10)
        raise ApiError("instagram", 408, "media container not ready in time")

    def publish_image(self, image_url: str, caption: str) -> dict:
        c = call(
            "instagram",
            "POST",
            f"{GRAPH}/{self.user_id}/media",
            params=self._p({"image_url": image_url, "caption": caption[:2200]}),
        )
        self._wait_ready(c["id"])
        return call(
            "instagram", "POST", f"{GRAPH}/{self.user_id}/media_publish", params=self._p({"creation_id": c["id"]})
        )

    def publish_reel(self, video_url: str, caption: str, cover_url: str | None = None, share_to_feed: bool = True) -> dict:
        params = {
            "media_type": "REELS",
            "video_url": video_url,
            "caption": caption[:2200],
            "share_to_feed": "true" if share_to_feed else "false",
        }
        if cover_url:
            params["cover_url"] = cover_url
        c = call("instagram", "POST", f"{GRAPH}/{self.user_id}/media", params=self._p(params))
        self._wait_ready(c["id"], timeout_s=600)
        return call(
            "instagram", "POST", f"{GRAPH}/{self.user_id}/media_publish", params=self._p({"creation_id": c["id"]})
        )

    def publish_carousel(self, image_urls: list[str], caption: str) -> dict:
        children = []
        for u in image_urls[:10]:
            c = call(
                "instagram",
                "POST",
                f"{GRAPH}/{self.user_id}/media",
                params=self._p({"image_url": u, "is_carousel_item": "true"}),
            )
            children.append(c["id"])
        c = call(
            "instagram",
            "POST",
            f"{GRAPH}/{self.user_id}/media",
            params=self._p({"media_type": "CAROUSEL", "children": ",".join(children), "caption": caption[:2200]}),
        )
        self._wait_ready(c["id"])
        return call(
            "instagram", "POST", f"{GRAPH}/{self.user_id}/media_publish", params=self._p({"creation_id": c["id"]})
        )
