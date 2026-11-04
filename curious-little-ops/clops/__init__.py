"""clops - Curious Little Ops.

Small, dependency-light toolkit that lets a scheduled Claude run act as the
marketing/ops brain for the Curious Little by Gozde business:

- state.py      : single JSON source of truth (products, KPIs, content queue, decisions)
- config.py     : secrets loading (env vars or a secrets.json kept in Google Drive)
- pinterest.py  : create pins, read analytics (Pinterest API v5)
- instagram.py  : publish images/reels (Meta Graph API)
- youtube.py    : upload Shorts (YouTube Data API v3)
- etsy.py       : shop receipts (sales), listings, price/state changes (Etsy Open API v3)
- kdp.py        : parse KDP royalty reports (no API exists, CSV/XLSX only)
- publisher.py  : drains the content queue to the right platform
- report.py     : weekly KPI delta + decision candidates
"""

__version__ = "0.1.0"
