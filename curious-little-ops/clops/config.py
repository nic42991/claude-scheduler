"""Secrets and settings.

Order of precedence:
1. Environment variables (CLOPS_PINTEREST_TOKEN, ...)
2. A JSON file whose path is in CLOPS_SECRETS_FILE (default: ./secrets.json)

The secrets file is NEVER committed. In the scheduled Claude run it is
downloaded from the private Google Drive folder "curious-little-ops" to the
working directory just before the scripts run.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

SECRET_KEYS = {
    # Pinterest API v5 - long-lived access token (from OAuth) + default board
    "pinterest_token": "CLOPS_PINTEREST_TOKEN",
    "pinterest_board_id": "CLOPS_PINTEREST_BOARD_ID",
    # Meta Graph API - long-lived Page token + Instagram Business account id
    "instagram_token": "CLOPS_INSTAGRAM_TOKEN",
    "instagram_user_id": "CLOPS_INSTAGRAM_USER_ID",
    # YouTube Data API v3 - OAuth client + refresh token
    "youtube_client_id": "CLOPS_YOUTUBE_CLIENT_ID",
    "youtube_client_secret": "CLOPS_YOUTUBE_CLIENT_SECRET",
    "youtube_refresh_token": "CLOPS_YOUTUBE_REFRESH_TOKEN",
    # Etsy Open API v3 - keystring + OAuth refresh token + shop id
    "etsy_keystring": "CLOPS_ETSY_KEYSTRING",
    "etsy_shared_secret": "CLOPS_ETSY_SHARED_SECRET",
    "etsy_refresh_token": "CLOPS_ETSY_REFRESH_TOKEN",
    "etsy_shop_id": "CLOPS_ETSY_SHOP_ID",
    # Public base URL where queued images can be fetched by Instagram/Pinterest.
    # Default: raw GitHub URL of this repo's assets/ folder (repo is public).
    "asset_base_url": "CLOPS_ASSET_BASE_URL",
}

DEFAULT_ASSET_BASE_URL = (
    "https://raw.githubusercontent.com/nic42991/claude-scheduler/main/curious-little-ops/assets/"
)


@dataclass
class Secrets:
    values: dict[str, str] = field(default_factory=dict)

    def get(self, key: str, default: str | None = None) -> str | None:
        return self.values.get(key) or default

    def require(self, *keys: str) -> list[str]:
        missing = [k for k in keys if not self.values.get(k)]
        if missing:
            raise MissingSecret(missing)
        return [self.values[k] for k in keys]

    def has(self, *keys: str) -> bool:
        return all(self.values.get(k) for k in keys)

    def status(self) -> dict[str, bool]:
        return {k: bool(self.values.get(k)) for k in SECRET_KEYS}


class MissingSecret(RuntimeError):
    def __init__(self, keys: list[str]):
        self.keys = keys
        super().__init__("missing secrets: " + ", ".join(keys))


def load_secrets(path: str | os.PathLike | None = None) -> Secrets:
    values: dict[str, str] = {}
    file_path = Path(path or os.environ.get("CLOPS_SECRETS_FILE", "secrets.json"))
    if file_path.exists():
        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                for k in SECRET_KEYS:
                    v = data.get(k)
                    if isinstance(v, str) and v and not v.startswith("<"):
                        values[k] = v
        except json.JSONDecodeError as e:
            raise RuntimeError(f"{file_path} is not valid JSON: {e}") from e
    for k, env in SECRET_KEYS.items():
        v = os.environ.get(env)
        if v:
            values[k] = v
    values.setdefault("asset_base_url", DEFAULT_ASSET_BASE_URL)
    return Secrets(values)


def secrets_template() -> dict[str, str]:
    """Template to hand to the user; placeholders start with '<' and are ignored."""
    return {k: f"<{k}>" for k in SECRET_KEYS if k != "asset_base_url"} | {
        "asset_base_url": DEFAULT_ASSET_BASE_URL
    }
