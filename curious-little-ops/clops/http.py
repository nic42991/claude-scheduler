"""Tiny HTTP helper around requests with retries and clear errors."""
from __future__ import annotations

import time
from typing import Any

import requests


class ApiError(RuntimeError):
    def __init__(self, platform: str, status: int, body: str):
        self.platform, self.status, self.body = platform, status, body
        super().__init__(f"{platform} API {status}: {body[:400]}")


def call(
    platform: str,
    method: str,
    url: str,
    *,
    headers: dict | None = None,
    params: dict | None = None,
    json: Any = None,
    data: Any = None,
    files: Any = None,
    retries: int = 2,
    timeout: int = 60,
) -> Any:
    last: Exception | None = None
    for attempt in range(retries + 1):
        try:
            r = requests.request(
                method, url, headers=headers, params=params, json=json, data=data, files=files, timeout=timeout
            )
        except requests.RequestException as e:  # network blip
            last = e
            time.sleep(2 * (attempt + 1))
            continue
        if r.status_code == 429 or r.status_code >= 500:
            last = ApiError(platform, r.status_code, r.text)
            time.sleep(5 * (attempt + 1))
            continue
        if r.status_code >= 400:
            raise ApiError(platform, r.status_code, r.text)
        if not r.content:
            return {}
        try:
            return r.json()
        except ValueError:
            return {"raw": r.text}
    assert last is not None
    raise last
