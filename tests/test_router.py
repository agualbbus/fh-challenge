"""Unit tests for `route_event` — broker guard + agent invocation seam."""

from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage

from app.customers.base import get_customer_profiles
from app.worker import agent as agent_module
from app.worker.graph import route_event

from tests._llm_stub import ScriptedChatModel, tool_call


@pytest.mark.asyncio
async def test_route_event_invokes_agent_and_records_tool_calls(
    base_load_state: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    get_customer_profiles()
    scripted = ScriptedChatModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    tool_call("get_load_info", {"field": "delivery_address"}),
                    tool_call(
                        "send_sms",
                        {
                            "recipient": "driver",
                            "message": "456 Delivery St, Dallas, TX",
                        },
                    ),
                ],
            ),
            AIMessage(
                content=(
                    "SUMMARY: Replied with delivery address.\n"
                    "RATIONALE: Driver asked for address."
                ),
            ),
        ]
    )
    monkeypatch.setattr(agent_module, "get_chat_model", lambda: scripted)

    event = {
        "event_id": "evt-3b",
        "event_type": "inbound_communication",
        "inbound_communication": {
            "channel": "sms",
            "sender_type": "driver",
            "content": "What's the delivery address?",
            "attachments": [],
        },
    }
    decision = await route_event(base_load_state, event)

    tools = [tc.tool for tc in decision.tool_calls]
    assert "send_sms" in tools
    assert decision.summary == "Replied with delivery address."


@pytest.mark.asyncio
async def test_broker_ignore(base_load_state: dict) -> None:
    event = {
        "event_id": "evt-broker",
        "event_type": "inbound_communication",
        "inbound_communication": {
            "channel": "email",
            "sender_type": "broker",
            "content": "Please update status",
            "attachments": [],
        },
    }
    decision = await route_event(base_load_state, event)
    assert decision.noop is True
    assert len(decision.tool_calls) == 0
    assert decision.reason == "broker message ignored"
