#!/usr/bin/env python3
"""Which credentials exist and which APIs answer. Safe to run any time (read-only)."""
from __future__ import annotations

import json

from _common import load

from clops.config import MissingSecret


def main() -> int:
    state, secrets = load()
    out = {"secrets": secrets.status(), "apis": {}, "state": {"products": len(state.products), "queued": state.queued_count(), "pending_decisions": len(state.pending_decisions())}}

    def probe(name, fn):
        try:
            out["apis"][name] = {"ok": True, "info": fn()}
        except MissingSecret as e:
            out["apis"][name] = {"ok": False, "missing": e.keys}
        except Exception as e:  # noqa: BLE001
            out["apis"][name] = {"ok": False, "error": str(e)[:200]}

    from clops.etsy import Etsy
    from clops.instagram import Instagram
    from clops.pinterest import Pinterest
    from clops.youtube import YouTube

    probe("pinterest", lambda: Pinterest(secrets).me().get("username"))
    probe("instagram", lambda: Instagram(secrets).account())
    probe("youtube", lambda: YouTube(secrets).channel_stats())
    probe("etsy", lambda: Etsy(secrets).shop().get("shop_name"))
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
