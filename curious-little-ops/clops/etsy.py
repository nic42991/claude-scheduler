"""Etsy Open API v3.

Setup (one time):
  1. etsy.com/developers -> create app -> wait for approval (usually 1-5 days) -> keystring + shared secret.
  2. Run scripts/etsy_auth.py once on your laptop (OAuth2 PKCE). It prints a refresh token
     and your shop id. Scopes: listings_r listings_w shops_r transactions_r feedback_r.
Store keystring, shared secret, refresh token, shop id in secrets.

Note: Etsy v3 exposes orders, listings, reviews and listing state/price, but NOT the
"views / visits / conversion" stats from Shop Manager. Those still come from Nick
pasting the Stats page or Claude reading it in his Chrome.
"""
from __future__ import annotations

import datetime as dt

from .config import Secrets
from .http import call

BASE = "https://openapi.etsy.com/v3/application"
TOKEN_URL = "https://api.etsy.com/v3/public/oauth/token"


class Etsy:
    def __init__(self, secrets: Secrets):
        self.keystring, self.refresh_token, self.shop_id = secrets.require(
            "etsy_keystring", "etsy_refresh_token", "etsy_shop_id"
        )
        self._access: str | None = None
        self.new_refresh_token: str | None = None  # Etsy rotates refresh tokens; persist this if set

    def _token(self) -> str:
        if self._access:
            return self._access
        r = call(
            "etsy",
            "POST",
            TOKEN_URL,
            data={"grant_type": "refresh_token", "client_id": self.keystring, "refresh_token": self.refresh_token},
        )
        self._access = r["access_token"]
        if r.get("refresh_token") and r["refresh_token"] != self.refresh_token:
            self.new_refresh_token = r["refresh_token"]
        return self._access

    def _h(self) -> dict:
        return {"x-api-key": self.keystring, "Authorization": f"Bearer {self._token()}"}

    # ---- read ----
    def shop(self) -> dict:
        return call("etsy", "GET", f"{BASE}/shops/{self.shop_id}", headers=self._h())

    def listings(self, state: str = "active", limit: int = 100) -> list[dict]:
        r = call(
            "etsy",
            "GET",
            f"{BASE}/shops/{self.shop_id}/listings",
            headers=self._h(),
            params={"state": state, "limit": limit, "includes": "Images"},
        )
        return r.get("results", [])

    def receipts(self, days: int = 7) -> list[dict]:
        since = int((dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)).timestamp())
        out, offset = [], 0
        while True:
            r = call(
                "etsy",
                "GET",
                f"{BASE}/shops/{self.shop_id}/receipts",
                headers=self._h(),
                params={"min_created": since, "limit": 100, "offset": offset},
            )
            res = r.get("results", [])
            out += res
            if len(res) < 100:
                return out
            offset += 100

    def reviews(self, limit: int = 100) -> list[dict]:
        r = call("etsy", "GET", f"{BASE}/shops/{self.shop_id}/reviews", headers=self._h(), params={"limit": limit})
        return r.get("results", [])

    def sales_summary(self, days: int = 7) -> dict:
        rs = self.receipts(days)
        orders = len(rs)
        revenue = 0.0
        by_listing: dict[str, int] = {}
        for rc in rs:
            g = rc.get("grandtotal") or {}
            revenue += (g.get("amount") or 0) / (g.get("divisor") or 100)
            for t in rc.get("transactions", []):
                lid = str(t.get("listing_id"))
                by_listing[lid] = by_listing.get(lid, 0) + int(t.get("quantity") or 1)
        return {"orders": orders, "revenue": round(revenue, 2), "by_listing": by_listing}

    # ---- write ----
    def set_listing_state(self, listing_id: int | str, state: str) -> dict:
        """state: 'active' or 'inactive' (hide without deleting)."""
        return call(
            "etsy",
            "PATCH",
            f"{BASE}/shops/{self.shop_id}/listings/{listing_id}",
            headers={**self._h(), "Content-Type": "application/x-www-form-urlencoded"},
            data={"state": state},
        )

    def set_listing_price(self, listing_id: int | str, price: float) -> dict:
        """Update the price on every offering of the listing (works for digital listings)."""
        inv = call("etsy", "GET", f"{BASE}/listings/{listing_id}/inventory", headers=self._h())
        products = []
        for p in inv.get("products", []):
            offerings = []
            for o in p.get("offerings", []):
                offerings.append({"price": float(price), "quantity": o.get("quantity", 999), "is_enabled": o.get("is_enabled", True)})
            products.append(
                {
                    "sku": p.get("sku", ""),
                    "property_values": [
                        {k: v for k, v in pv.items() if k in {"property_id", "property_name", "value_ids", "values", "scale_id"}}
                        for pv in p.get("property_values", [])
                    ],
                    "offerings": offerings,
                }
            )
        body = {"products": products}
        for k in ("price_on_property", "quantity_on_property", "sku_on_property"):
            if inv.get(k):
                body[k] = inv[k]
        return call(
            "etsy",
            "PUT",
            f"{BASE}/listings/{listing_id}/inventory",
            headers={**self._h(), "Content-Type": "application/json"},
            json=body,
        )
