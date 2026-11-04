"""Pinterest API v5.

Setup (one time): developers.pinterest.com -> create app -> OAuth with scopes
  boards:read, pins:read, pins:write, user_accounts:read
and store the access token as pinterest_token. Pinterest tokens from the
"trial" app type still allow posting to your own account.
"""
from __future__ import annotations

import base64
import datetime as dt
from pathlib import Path

from .config import Secrets
from .http import call

BASE = "https://api.pinterest.com/v5"


class Pinterest:
    def __init__(self, secrets: Secrets):
        (self.token,) = secrets.require("pinterest_token")
        self.default_board = secrets.get("pinterest_board_id")
        self.h = {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}

    # ---- read ----
    def me(self) -> dict:
        return call("pinterest", "GET", f"{BASE}/user_account", headers=self.h)

    def boards(self) -> list[dict]:
        out, bookmark = [], None
        while True:
            params = {"page_size": 100}
            if bookmark:
                params["bookmark"] = bookmark
            r = call("pinterest", "GET", f"{BASE}/boards", headers=self.h, params=params)
            out += r.get("items", [])
            bookmark = r.get("bookmark")
            if not bookmark:
                return out

    def analytics(self, days: int = 7) -> dict:
        """Account-level totals for the last `days` days.

        Returns {"impressions": int, "outbound_clicks": int, "pin_clicks": int, "saves": int}
        """
        end = dt.date.today()
        start = end - dt.timedelta(days=days)
        r = call(
            "pinterest",
            "GET",
            f"{BASE}/user_account/analytics",
            headers=self.h,
            params={
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
                "metric_types": "IMPRESSION,OUTBOUND_CLICK,PIN_CLICK,SAVE",
            },
        )
        summary = (r.get("all") or {}).get("summary_metrics") or {}
        return {
            "impressions": int(summary.get("IMPRESSION", 0) or 0),
            "outbound_clicks": int(summary.get("OUTBOUND_CLICK", 0) or 0),
            "pin_clicks": int(summary.get("PIN_CLICK", 0) or 0),
            "saves": int(summary.get("SAVE", 0) or 0),
        }

    # ---- write ----
    def create_pin(
        self,
        *,
        title: str,
        description: str,
        link: str,
        image_url: str | None = None,
        image_path: str | Path | None = None,
        board_id: str | None = None,
        alt_text: str | None = None,
    ) -> dict:
        board = board_id or self.default_board
        if not board:
            raise RuntimeError("no Pinterest board id (set pinterest_board_id or pass board_id)")
        if image_path:
            p = Path(image_path)
            ctype = "image/png" if p.suffix.lower() == ".png" else "image/jpeg"
            media = {
                "source_type": "image_base64",
                "content_type": ctype,
                "data": base64.b64encode(p.read_bytes()).decode(),
            }
        elif image_url:
            media = {"source_type": "image_url", "url": image_url}
        else:
            raise RuntimeError("create_pin needs image_url or image_path")
        body = {
            "board_id": board,
            "title": title[:100],
            "description": description[:800],
            "link": link,
            "media_source": media,
        }
        if alt_text:
            body["alt_text"] = alt_text[:500]
        return call("pinterest", "POST", f"{BASE}/pins", headers=self.h, json=body)
