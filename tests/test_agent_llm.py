"""Demonstrate LLM injection via FakeListLLM for deterministic unit tests.

FakeListLLM is a text-only LLM (no `bind_tools`), so it can't drive `create_agent`
end-to-end — for tool-calling coverage the suite relies on `MODEL_MODE=mock` and
`MockToolCallingModel`. These tests pin the LLM-substitution seam itself: anything
that calls `app.worker.llm.get_chat_model()` can be swapped out cleanly, which is
the contract evals and live/mocked parity depend on.
"""

from __future__ import annotations

import pytest
from langchain_core.language_models.fake import FakeListLLM

from app.worker import llm as llm_module


@pytest.fixture
def fake_llm(monkeypatch: pytest.MonkeyPatch) -> FakeListLLM:
    fake = FakeListLLM(responses=["first scripted reply", "second scripted reply"])
    monkeypatch.setattr(llm_module, "get_chat_model", lambda: fake)
    return fake


def test_get_chat_model_is_swappable(fake_llm: FakeListLLM) -> None:
    assert llm_module.get_chat_model() is fake_llm


def test_fake_llm_returns_scripted_responses_in_order(fake_llm: FakeListLLM) -> None:
    assert fake_llm.invoke("ignored prompt 1") == "first scripted reply"
    assert fake_llm.invoke("ignored prompt 2") == "second scripted reply"


def test_fake_llm_cycles_responses_when_exhausted() -> None:
    fake = FakeListLLM(responses=["only one"])
    assert fake.invoke("a") == "only one"
    # FakeListLLM cycles back to index 0 once the script is consumed.
    assert fake.invoke("b") == "only one"
