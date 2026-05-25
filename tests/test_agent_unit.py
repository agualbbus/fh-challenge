"""Agent helpers and error branches in isolation."""

from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from app.worker import agent as agent_module
from app.worker.agent import (
    _format_customer_profile,
    _message_text,
    build_system_prompt,
    parse_final_answer,
    route_event,
)
from app.customers.base import get_customer_profile


def test_parse_final_answer_extracts_both() -> None:
    msgs = [
        HumanMessage(content="hi"),
        AIMessage(content="SUMMARY: did x\nRATIONALE: because y"),
    ]
    summary, rationale = parse_final_answer(msgs)
    assert summary == "did x"
    assert rationale == "because y"


def test_parse_final_answer_returns_empty_when_missing() -> None:
    assert parse_final_answer([AIMessage(content="nothing here")]) == ("", "")
    assert parse_final_answer([]) == ("", "")


def test_message_text_handles_block_list() -> None:
    msg = AIMessage(content=[{"type": "text", "text": "part1"}, "part2"])
    assert "part1" in _message_text(msg)
    assert "part2" in _message_text(msg)


def test_format_customer_profile_renders_known_customer() -> None:
    profile = get_customer_profile("customer_a")
    text = _format_customer_profile(profile)
    assert "customer_a" in text
    assert "geofence" in text.lower() or "miles" in text


def test_build_system_prompt_raises_without_customer() -> None:
    with pytest.raises(ValueError, match="customer_id"):
        build_system_prompt({}, {})


def test_build_system_prompt_raises_without_active_task() -> None:
    with pytest.raises(ValueError, match="active_task"):
        build_system_prompt({"customer_id": "customer_a"}, {})


def test_build_system_prompt_includes_sop_and_event() -> None:
    prompt = build_system_prompt(
        {
            "customer_id": "customer_a",
            "active_task": "delivery_eta_checkpoint",
            "milestone": "on_route_to_delivery",
        },
        {"event_id": "e1", "event_type": "inbound_communication"},
    )
    assert "<sop" in prompt
    assert "<incoming_event>" in prompt
    assert "<customer_profile" in prompt


@pytest.mark.asyncio
async def test_route_event_short_circuits_broker_messages() -> None:
    decision = await route_event(
        {"customer_id": "customer_a", "active_task": "confirm_delivery"},
        {
            "event_type": "inbound_communication",
            "inbound_communication": {"sender_type": "broker"},
        },
    )
    assert decision.noop is True
    assert "broker" in decision.reason


@pytest.mark.asyncio
async def test_route_event_unhandled_event_type_is_noop() -> None:
    decision = await route_event({}, {"event_type": "weird"})
    assert decision.noop is True
    assert decision.tool_calls == []


@pytest.mark.asyncio
async def test_run_agent_for_event_catches_llm_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    class Boom:
        async def ainvoke(self, *_a, **_kw):
            raise RuntimeError("LLM exploded")

    monkeypatch.setattr(agent_module, "build_agent", lambda: Boom())
    decision = await agent_module.run_agent_for_event(
        {
            "load_id": "L1",
            "customer_id": "customer_a",
            "active_task": "delivery_eta_checkpoint",
        },
        {},
        {"event_id": "e1", "event_type": "inbound_communication"},
    )
    assert decision.noop is True
    assert "LLM exploded" in decision.reason
