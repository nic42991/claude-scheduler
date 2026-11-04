#!/usr/bin/env python3
"""Add content to the queue from a JSON file (Claude writes the JSON, this validates and stores it).

  python3 scripts/enqueue.py items.json
  python3 scripts/enqueue.py --make-image product.jpg "Headline" out.jpg   # helper to build a pin card

items.json = [
  {"platform": "pinterest", "scheduled_for": "2026-11-06", "title": "...", "text": "...", "link": "https://...", "image": "pin-xmas-bundle-1.jpg", "product_id": "P-..."},
  {"platform": "instagram", "scheduled_for": "2026-11-07", "title": "...", "text": "...", "image": "ig-....jpg"},
  {"platform": "instagram_reel", "scheduled_for": "2026-11-08", "title": "...", "text": "...", "video": "reel-....mp4", "image": "cover.jpg"},
  {"platform": "youtube_short", "scheduled_for": "2026-11-09", "title": "...", "text": "...", "video": "short-....mp4", "tags": ["kids song"]}
]
"""
from __future__ import annotations

import json
import sys

from _common import load

from clops.publisher import asset_path

REQUIRED = {
    "pinterest": ["title", "text", "link", "image"],
    "instagram": ["text", "image"],
    "instagram_reel": ["text", "video"],
    "youtube_short": ["title", "text", "video"],
}


def main() -> int:
    if len(sys.argv) >= 2 and sys.argv[1] == "--make-image":
        from clops.images import make_pin

        _, _, src, headline, out = sys.argv[:5]
        print(make_pin(src, headline, out))
        return 0
    items = json.load(open(sys.argv[1], encoding="utf-8"))
    state, _ = load()
    added, bad = [], []
    for it in items:
        plat = it.get("platform")
        miss = [k for k in REQUIRED.get(plat, ["?"]) if not it.get(k)]
        if miss or not it.get("scheduled_for"):
            bad.append((it.get("title", "?"), f"missing {miss or ['scheduled_for']}"))
            continue
        for key in ("image", "video"):
            v = it.get(key)
            if v and not v.startswith("http") and asset_path(v) is None:
                it["status_note"] = f"{key} {v} not in assets/ yet"
        q = state.enqueue(plat, it.pop("scheduled_for"), **{k: v for k, v in it.items() if k != "platform"})
        added.append(q["id"])
    state.save()
    print(json.dumps({"added": added, "rejected": bad, "queued_total": state.queued_count()}, ensure_ascii=False, indent=2))
    return 0 if not bad else 1


if __name__ == "__main__":
    raise SystemExit(main())
