#!/usr/bin/env python3
"""One-time Pinterest OAuth. Run on your laptop:

  pip install requests
  python3 scripts/pinterest_auth.py <APP_ID> <APP_SECRET>

Register redirect URI http://localhost:8767/callback in the Pinterest app.
Prints a long-lived access token (valid 30 days) + refresh token (1 year) + your boards.
Put the access token in pinterest_token and the board id you want pins on in pinterest_board_id.
"""
from __future__ import annotations

import base64
import http.server
import sys
import urllib.parse
import webbrowser

import requests

SCOPE = "boards:read,pins:read,pins:write,user_accounts:read"
REDIRECT = "http://localhost:8767/callback"


def main() -> int:
    app_id, app_secret = sys.argv[1], sys.argv[2]
    url = "https://www.pinterest.com/oauth/?" + urllib.parse.urlencode(
        {"client_id": app_id, "redirect_uri": REDIRECT, "response_type": "code", "scope": SCOPE, "state": "clops"}
    )
    print("Opening:", url)
    webbrowser.open(url)
    box = {}

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            box["code"] = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).get("code", [""])[0]
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK - you can close this tab.")

        def log_message(self, *a):
            pass

    http.server.HTTPServer(("localhost", 8767), H).handle_request()
    basic = base64.b64encode(f"{app_id}:{app_secret}".encode()).decode()
    r = requests.post(
        "https://api.pinterest.com/v5/oauth/token",
        headers={"Authorization": "Basic " + basic, "Content-Type": "application/x-www-form-urlencoded"},
        data={"grant_type": "authorization_code", "code": box["code"], "redirect_uri": REDIRECT},
        timeout=30,
    )
    r.raise_for_status()
    tok = r.json()
    boards = requests.get("https://api.pinterest.com/v5/boards", headers={"Authorization": "Bearer " + tok["access_token"]}, timeout=30).json()
    print("\nBoards:")
    for b in boards.get("items", []):
        print(f"  {b['id']}  {b['name']}")
    print("\nPaste into secrets.json:")
    print('  "pinterest_token":', f'"{tok["access_token"]}",')
    print('  "pinterest_board_id": "<pick a board id above>"')
    print("\nrefresh_token (keep somewhere safe, needed to renew after 30 days):", tok.get("refresh_token"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
