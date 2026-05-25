"""API-key dependency."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.api.auth import require_api_key


def test_require_api_key_disabled_when_env_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("API_KEY", raising=False)
    require_api_key(x_api_key=None)


def test_require_api_key_rejects_when_missing_header(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("API_KEY", "secret")
    with pytest.raises(HTTPException) as exc:
        require_api_key(x_api_key=None)
    assert exc.value.status_code == 401


def test_require_api_key_rejects_wrong_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("API_KEY", "secret")
    with pytest.raises(HTTPException):
        require_api_key(x_api_key="nope")


def test_require_api_key_accepts_match(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("API_KEY", "secret")
    require_api_key(x_api_key="secret")
