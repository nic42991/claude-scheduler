#!/usr/bin/env python3
"""One-time YouTube OAuth. Run on your laptop:

  pip install requests
  python3 scripts/youtube_auth.py <CLIENT_ID> <CLIENT_SECRET>

Redirect URI http://localhost:8766/callback must be allowed on the OAuth client
(Desktop-app clients allow any localhost port). Prints the refresh token.
"""
from __future__ import annotations

import http.server
import sys
import urllib.parse
import webbrowser

import requests

SCOPE = "https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube.readonly"
REDIRECT = "http://localhost:8766/callback"


def main() -> int:
    cid, csec = sys.argv[1], sys.argv[2]
    url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(
        {"client_id": cid, "redirect_uri": REDIRECT, "response_type": "code", "scope": SCOPE, "access_type": "offline", "prompt": "consent"}
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

    http.server.HTTPServer(("localhost", 8766), H).handle_request()
    r = requests.post(
        "https://oauth2.googleapis.com/token",
        data={"code": box["code"], "client_id": cid, "client_secret": csec, "redirect_uri": REDIRECT, "grant_type": "authorization_code"},
        timeout=30,
    )
    r.raise_for_status()
    print("\nPaste into secrets.json:")
    print('  "youtube_client_id":', f'"{cid}",')
    print('  "youtube_client_secret":', f'"{csec}",')
    print('  "youtube_refresh_token":', f'"{r.json()["refresh_token"]}"')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
