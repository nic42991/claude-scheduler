#!/usr/bin/env python3
"""Publish everything in the queue that is due today.

  python3 scripts/daily_post.py [--dry-run] [--date YYYY-MM-DD]

Reads state.json (CLOPS_STATE_FILE) + secrets.json (CLOPS_SECRETS_FILE), writes state.json back.
Prints a JSON summary; exit 0 even on partial failure (failures are recorded in state).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json

from _common import load

from clops.publisher import drain


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--date")
    a = ap.parse_args()
    state, secrets = load()
    on = dt.date.fromisoformat(a.date) if a.date else None
    summary = drain(state, secrets, on=on, dry_run=a.dry_run)
    if not a.dry_run:
        state.prune_queue()
        state.save()
    summary["queued_left"] = state.queued_count()
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
