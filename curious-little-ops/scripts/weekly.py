#!/usr/bin/env python3
"""Weekly CEO run, mechanical part.

  python3 scripts/weekly.py [--kdp-report path.xlsx] [--manual key=value ...] [--approvals file.txt] [--out brief.md]

1. applies approvals parsed from email reply text (file with one reply per block)
2. records manual KPIs Claude extracted (e.g. --manual etsy_visits=2810 ads_spend=35 ads_sales=20)
3. collects API KPIs
4. runs rules -> proposals (money decisions become pending approvals)
5. writes brief markdown
"""
from __future__ import annotations

import argparse
import json

from _common import load

from clops.report import brief_markdown, collect, rules
from clops.state import apply_email_approvals


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kdp-report")
    ap.add_argument("--manual", nargs="*", default=[])
    ap.add_argument("--approvals")
    ap.add_argument("--out", default="brief.md")
    ap.add_argument("--week")
    a = ap.parse_args()
    state, secrets = load()

    applied = []
    if a.approvals:
        text = open(a.approvals, encoding="utf-8").read()
        applied = apply_email_approvals(state, text.split("\n\n---\n\n"))
    for kv in a.manual:
        k, _, v = kv.partition("=")
        try:
            val = float(v) if "." in v else int(v)
        except ValueError:
            val = v
        state.record_kpi(k, val, "manual", a.week)

    problems = collect(state, secrets, kdp_report=a.kdp_report, week=a.week)
    cands = rules(state)
    created = []
    for c in cands:
        # avoid duplicate pending proposals of the same type/text
        if any(d["proposal"] == c["proposal"] and d["status"] == "proposed" for d in state.decisions):
            continue
        created.append(state.propose(c["type"], c["proposal"], needs_approval=c["needs_approval"], why=c.get("why", "")))
    brief = brief_markdown(state, problems, cands)
    open(a.out, "w", encoding="utf-8").write(brief)
    state.log("weekly", f"brief written; {len(created)} proposals; approvals {applied}")
    state.save()
    print(json.dumps({"approvals_applied": applied, "proposals_created": [d["id"] for d in created], "problems": problems, "brief": a.out}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
