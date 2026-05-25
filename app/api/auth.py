"""API-key authentication for write endpoints.

Reads the expected key from `API_KEY` (env / Secrets Manager). When unset,
auth is disabled — used by local dev and tests. When set, requests must
present a matching `X-API-Key` header.
"""

from __future__ import annotations

import hmac
import os

from fastapi import Header, HTTPException, status


def _expected_key() -> str | None:
    key = os.getenv("API_KEY", "").strip()
    return key or None


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    expected = _expected_key()
    if expected is None:
        return
    if x_api_key is None or not hmac.compare_digest(x_api_key, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-API-Key",
        )
