#!/usr/bin/env python3
"""One-time Etsy OAuth2 (PKCE). Run on your laptop:

  pip install requests
  python3 scripts/etsy_auth.py <KEYSTRING>

Opens a browser, you approve, it prints refresh_token + shop_id to paste into secrets.json.
Redirect URI must be registered in your Etsy app as http://localhost:8765/callback
"""
from __future__ import annotations

import base64
import hashlib
import http.server
import secrets as pysecrets
import sys
import urllib.parse
import webbrowser

import requests

SCOPES = "listings_r listings_w shops_r transactions_r feedback_r"
REDIRECT = "http://localhost:8765/callback"


def main() -> int:
    key = sys.argv[1]
    verifier = base64.urlsafe_b64encode(pysecrets.token_bytes(32)).rstrip(b"=").decode()
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    st = pysecrets.token_hex(8)
    url = "https://www.etsy.com/oauth/connect?" + urllib.parse.urlencode(
        {"response_type": "code", "redirect_uri": REDIRECT, "scope": SCOPES, "client_id": key, "state": st, "code_challenge": challenge, "code_challenge_method": "S256"}
    )
    print("Opening:", url)
    webbrowser.open(url)
    code_box = {}

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            code_box["code"] = q.get("code", [""])[0]
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK - you can close this tab.")

        def log_message(self, *a):  # silence
            pass

    http.server.HTTPServer(("localhost", 8765), H).handle_request()
    r = requests.post(
        "https://api.etsy.com/v3/public/oauth/token",
        data={"grant_type": "authorization_code", "client_id": key, "redirect_uri": REDIRECT, "code": code_box["code"], "code_verifier": verifier},
        timeout=30,
    )
    r.raise_for_status()
    tok = r.json()
    user_id = tok["access_token"].split(".")[0]
    h = {"x-api-key": key, "Authorization": "Bearer " + tok["access_token"]}
    shop = requests.get(f"https://openapi.etsy.com/v3/application/users/{user_id}/shops", headers=h, timeout=30).json()
    print("\nPaste into secrets.json:")
    print('  "etsy_keystring":', f'"{key}",')
    print('  "etsy_refresh_token":', f'"{tok["refresh_token"]}",')
    print('  "etsy_shop_id":', f'"{shop.get("shop_id")}"  # shop: {shop.get("shop_name")}')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
