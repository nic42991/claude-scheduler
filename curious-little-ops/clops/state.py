"""Single JSON source of truth for the business.

The file lives in Google Drive (folder "curious-little-ops", file "state.json").
A scheduled run downloads it, works on it with this module, and uploads it back.

Top-level keys:
  meta       - brand info, links, last update
  strategy   - current phase, standing rules, paused initiatives, targets
  products   - every product with platform, status (focus/live/hidden/draft)
  kpis       - one row per ISO week
  queue      - content queue (pins, reels, shorts) with scheduling + status
  decisions  - money/strategy decisions that need Nick's approval
  log        - short run log (kept to last 200 lines)
"""
from __future__ import annotations

import datetime as dt
import json
import uuid
from pathlib import Path
from typing import Any

STATE_VERSION = 1


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def today(tz: str = "America/New_York") -> dt.date:
    import zoneinfo

    return dt.datetime.now(zoneinfo.ZoneInfo(tz)).date()


def iso_week(d: dt.date | None = None) -> str:
    d = d or today()
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:6]}"


def empty_state() -> dict[str, Any]:
    return {
        "meta": {"version": STATE_VERSION, "updated": now_iso(), "brand": "", "links": {}},
        "strategy": {"phase": "", "phase_until": "", "rules": [], "paused": [], "targets": {}},
        "products": [],
        "kpis": [],
        "queue": [],
        "decisions": [],
        "log": [],
    }


class State:
    def __init__(self, data: dict[str, Any], path: Path | None = None):
        base = empty_state()
        base.update(data or {})
        self.data = base
        self.path = path

    # ---------- io ----------
    @classmethod
    def load(cls, path: str | Path) -> "State":
        p = Path(path)
        if not p.exists():
            return cls(empty_state(), p)
        return cls(json.loads(p.read_text(encoding="utf-8")), p)

    def save(self, path: str | Path | None = None) -> Path:
        p = Path(path or self.path or "state.json")
        self.data["meta"]["updated"] = now_iso()
        self.data["log"] = self.data["log"][-200:]
        p.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")
        self.path = p
        return p

    def log(self, run: str, msg: str) -> None:
        self.data["log"].append({"ts": now_iso(), "run": run, "msg": msg})

    # ---------- products ----------
    @property
    def products(self) -> list[dict]:
        return self.data["products"]

    def product(self, product_id: str) -> dict | None:
        return next((p for p in self.products if p.get("id") == product_id), None)

    def focus_products(self, platform: str | None = None) -> list[dict]:
        return [
            p
            for p in self.products
            if p.get("status") == "focus" and (platform is None or p.get("platform") == platform)
        ]

    def add_product(self, **fields: Any) -> dict:
        fields.setdefault("id", new_id("P"))
        fields.setdefault("status", "live")
        fields.setdefault("keywords", [])
        self.products.append(fields)
        return fields

    # ---------- kpis ----------
    @property
    def kpis(self) -> list[dict]:
        return self.data["kpis"]

    def kpi_row(self, week: str | None = None, create: bool = True) -> dict:
        week = week or iso_week()
        row = next((r for r in self.kpis if r.get("week") == week), None)
        if row is None and create:
            row = {"week": week, "source": {}}
            self.kpis.append(row)
            self.kpis.sort(key=lambda r: r["week"])
        return row

    def record_kpi(self, metric: str, value: float | int | None, source: str, week: str | None = None) -> None:
        if value is None:
            return
        row = self.kpi_row(week)
        row[metric] = value
        row["source"][metric] = source

    def last_two_weeks(self) -> tuple[dict | None, dict | None]:
        rows = sorted(self.kpis, key=lambda r: r["week"])
        if not rows:
            return None, None
        if len(rows) == 1:
            return rows[-1], None
        return rows[-1], rows[-2]

    # ---------- queue ----------
    @property
    def queue(self) -> list[dict]:
        return self.data["queue"]

    def enqueue(self, platform: str, scheduled_for: str, **fields: Any) -> dict:
        item = {
            "id": new_id("Q"),
            "platform": platform,
            "scheduled_for": scheduled_for,
            "status": "queued",
            "created": now_iso(),
            **fields,
        }
        self.queue.append(item)
        return item

    def due_items(self, on: dt.date | None = None) -> list[dict]:
        on = on or today()
        return [
            q
            for q in self.queue
            if q.get("status") == "queued" and q.get("scheduled_for", "9999-12-31") <= on.isoformat()
        ]

    def queued_count(self, platform: str | None = None) -> int:
        return sum(
            1
            for q in self.queue
            if q.get("status") == "queued" and (platform is None or q.get("platform") == platform)
        )

    def prune_queue(self, keep_days: int = 60) -> None:
        cutoff = (today() - dt.timedelta(days=keep_days)).isoformat()
        self.data["queue"] = [
            q for q in self.queue if q.get("status") == "queued" or q.get("scheduled_for", "") >= cutoff
        ]

    # ---------- decisions ----------
    @property
    def decisions(self) -> list[dict]:
        return self.data["decisions"]

    def propose(self, kind: str, proposal: str, needs_approval: bool = True, **fields: Any) -> dict:
        d = {
            "id": new_id("D"),
            "date": today().isoformat(),
            "type": kind,
            "proposal": proposal,
            "needs_approval": needs_approval,
            "status": "proposed" if needs_approval else "approved",
            **fields,
        }
        self.decisions.append(d)
        return d

    def set_decision(self, decision_id: str, status: str, note: str = "") -> dict | None:
        d = next((x for x in self.decisions if x["id"] == decision_id), None)
        if d:
            d["status"] = status
            d["status_changed"] = now_iso()
            if note:
                d["note"] = note
        return d

    def pending_decisions(self) -> list[dict]:
        return [d for d in self.decisions if d.get("status") == "proposed"]

    def approved_unexecuted(self) -> list[dict]:
        return [d for d in self.decisions if d.get("status") == "approved"]


def apply_email_approvals(state: State, email_bodies: list[str]) -> list[tuple[str, str]]:
    """Parse replies like 'approve D-1a2b3c' / 'reject D-1a2b3c' / 'onayla D-..' / 'red D-..'.

    Returns list of (decision_id, new_status) applied.
    """
    import re

    applied: list[tuple[str, str]] = []
    pat = re.compile(r"\b(approve|onayla|ok|evet|yes|reject|red|hayir|hayır|no)\b[^\n]*?\b(D-[0-9a-f]{6})\b", re.I)
    for body in email_bodies:
        for verb, did in pat.findall(body or ""):
            status = "approved" if verb.lower() in {"approve", "onayla", "ok", "evet", "yes"} else "rejected"
            if state.set_decision(did, status, note="via email reply"):
                applied.append((did, status))
    return applied
