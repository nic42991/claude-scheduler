"""Amazon KDP has no API. This parses the royalty / orders report you download from
kdpreports.amazon.com (Reports -> Generate Report -> Orders or Royalties, xlsx or csv)
and drops into the Drive folder "curious-little-ops/reports/".

The file name does not matter; we read every sheet and look for the usual columns.
"""
from __future__ import annotations

import csv
import io
from pathlib import Path


def _rows_from_file(path: Path) -> list[dict]:
    if path.suffix.lower() in {".xlsx", ".xlsm"}:
        import openpyxl  # lazy

        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        rows: list[dict] = []
        for ws in wb.worksheets:
            it = ws.iter_rows(values_only=True)
            header = None
            for r in it:
                if header is None:
                    if r and any(isinstance(c, str) and c.strip().lower() in {"title", "asin", "asin/isbn"} for c in r):
                        header = [str(c).strip() if c is not None else "" for c in r]
                    continue
                if r and any(c is not None for c in r):
                    rows.append(dict(zip(header, r)))
        return rows
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    return list(csv.DictReader(io.StringIO(text)))


def _num(v) -> float:
    if v is None or v == "":
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).replace(",", "").replace("$", "").strip()
    try:
        return float(s)
    except ValueError:
        return 0.0


def summarize(path: str | Path) -> dict:
    """Returns {"units": int, "royalty": float, "by_title": {title: {"units":..,"royalty":..}}}."""
    rows = _rows_from_file(Path(path))
    by: dict[str, dict] = {}
    for r in rows:
        keys = {k.lower().strip(): k for k in r if k}
        title = str(r.get(keys.get("title", ""), "") or "").strip()
        if not title:
            continue
        units = 0.0
        for cand in ("net units sold", "units sold", "net units", "orders", "units"):
            if cand in keys:
                units = _num(r.get(keys[cand]))
                break
        royalty = 0.0
        for cand in ("royalty", "royalty (usd)", "royalties", "net royalty"):
            if cand in keys:
                royalty = _num(r.get(keys[cand]))
                break
        b = by.setdefault(title, {"units": 0, "royalty": 0.0})
        b["units"] += int(units)
        b["royalty"] += royalty
    return {
        "units": sum(b["units"] for b in by.values()),
        "royalty": round(sum(b["royalty"] for b in by.values()), 2),
        "by_title": {t: {"units": b["units"], "royalty": round(b["royalty"], 2)} for t, b in by.items()},
    }
