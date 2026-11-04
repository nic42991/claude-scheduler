"""Drain the content queue: publish everything due today to its platform.

Queue item fields:
  platform      pinterest | instagram | instagram_reel | youtube_short
  scheduled_for YYYY-MM-DD
  title, text   headline + body/caption/description
  link          destination URL (Etsy listing, Amazon book, ...)
  image         file name under assets/ (public via asset_base_url) or an absolute https URL
  video         file name under assets/ (for reels/shorts) or https URL (reels only)
  tags          list[str] (youtube)
  board_id      optional pinterest board override
  product_id    optional link back to products[]
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

from .config import MissingSecret, Secrets
from .http import ApiError
from .state import State, now_iso

ASSETS = Path(__file__).resolve().parent.parent / "assets"


def asset_url(secrets: Secrets, name: str) -> str:
    if name.startswith("http://") or name.startswith("https://"):
        return name
    base = secrets.get("asset_base_url") or ""
    return base.rstrip("/") + "/" + name.lstrip("/")


def asset_path(name: str) -> Path | None:
    if name.startswith("http"):
        return None
    p = ASSETS / name
    return p if p.exists() else None


def publish_item(item: dict, secrets: Secrets, dry_run: bool = False) -> dict:
    plat = item["platform"]
    if dry_run:
        return {"dry_run": True, "platform": plat}
    if plat == "pinterest":
        from .pinterest import Pinterest

        pin = Pinterest(secrets)
        local = asset_path(item.get("image", ""))
        return pin.create_pin(
            title=item.get("title", ""),
            description=item.get("text", ""),
            link=item.get("link", ""),
            image_path=local,
            image_url=None if local else asset_url(secrets, item["image"]),
            board_id=item.get("board_id"),
            alt_text=item.get("alt_text") or item.get("title"),
        )
    if plat == "instagram":
        from .instagram import Instagram

        ig = Instagram(secrets)
        images = item.get("images") or [item["image"]]
        caption = (item.get("title", "") + "\n\n" + item.get("text", "")).strip()
        if len(images) > 1:
            return ig.publish_carousel([asset_url(secrets, i) for i in images], caption)
        return ig.publish_image(asset_url(secrets, images[0]), caption)
    if plat == "instagram_reel":
        from .instagram import Instagram

        ig = Instagram(secrets)
        caption = (item.get("title", "") + "\n\n" + item.get("text", "")).strip()
        cover = asset_url(secrets, item["image"]) if item.get("image") else None
        return ig.publish_reel(asset_url(secrets, item["video"]), caption, cover_url=cover)
    if plat == "youtube_short":
        from .youtube import YouTube

        yt = YouTube(secrets)
        local = asset_path(item.get("video", ""))
        if not local:
            raise RuntimeError("youtube_short needs a local video file under assets/")
        title = item.get("title", "")
        if "#shorts" not in title.lower():
            title = (title + " #Shorts")[:100]
        return yt.upload(local, title=title, description=item.get("text", ""), tags=item.get("tags"))
    raise RuntimeError(f"unknown platform {plat}")


def drain(state: State, secrets: Secrets, *, on: dt.date | None = None, dry_run: bool = False, max_items: int = 8) -> dict:
    """Publish due items. Returns summary {"posted": [...], "failed": [...], "skipped": [...]}."""
    summary: dict[str, list] = {"posted": [], "failed": [], "skipped": []}
    for item in state.due_items(on)[:max_items]:
        try:
            res = publish_item(item, secrets, dry_run=dry_run)
            if dry_run:
                summary["skipped"].append((item["id"], "dry run"))
                continue
            item["status"] = "posted"
            item["posted_at"] = now_iso()
            item["result"] = {k: res.get(k) for k in ("id", "link", "permalink") if isinstance(res, dict) and k in res}
            summary["posted"].append(item["id"])
            state.log("daily", f"posted {item['platform']} {item['id']}")
        except MissingSecret as e:
            item["status"] = "queued"  # leave for when credentials exist
            summary["skipped"].append((item["id"], f"missing secrets {e.keys}"))
        except (ApiError, RuntimeError, OSError) as e:
            item["attempts"] = int(item.get("attempts", 0)) + 1
            item["last_error"] = str(e)[:400]
            if item["attempts"] >= 3:
                item["status"] = "failed"
            summary["failed"].append((item["id"], str(e)[:200]))
            state.log("daily", f"FAILED {item['platform']} {item['id']}: {str(e)[:120]}")
    return summary
