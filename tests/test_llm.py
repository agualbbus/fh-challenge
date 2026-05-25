"""LLM factory."""

from __future__ import annotations

import pytest

from app.worker import llm


def test_get_chat_model_raises_without_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="OPENROUTER_API_KEY"):
        llm.get_chat_model()


def test_get_chat_model_constructs_when_key_present(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    model = llm.get_chat_model()
    assert model is not None
