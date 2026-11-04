# Curious Little Ops

Autopilot for the Curious Little by Gozde business (Etsy + Amazon KDP + Pinterest + Instagram + YouTube), run by two scheduled Claude tasks.

```
state.json (Google Drive)  <- single source of truth: products, KPIs, content queue, decisions
secrets.json (Google Drive) <- API tokens, never in git
clops/                      <- API clients + queue + weekly report rules
scripts/                    <- weekly.py (CEO pass), daily_post.py (publish), enqueue.py, check_setup.py, *_auth.py
prompts/                    <- the two scheduled-task instructions
assets/                     <- pin/post images, public via raw.githubusercontent.com
```

Weekly (Monday): read Nick's email replies (approvals, KPIs, instructions) -> collect KPIs -> rules + CEO judgment -> execute approved decisions -> fill next week's content queue -> email brief.

Daily: publish due queue items -> save state -> email only on problems.

Setup: see SETUP.md (Turkish).

Local dry run:
```
pip install -r requirements.txt
cp state.seed.json state.json
python3 scripts/check_setup.py
python3 scripts/weekly.py --manual etsy_visits=2800 etsy_orders=0 --out brief.md
python3 scripts/daily_post.py --dry-run
```
