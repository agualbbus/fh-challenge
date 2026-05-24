"""Unit tests for agent orchestrator (3b / 3c)."""

from __future__ import annotations

import copy

import pytest

from app.customers.base import get_customer_profiles
from app.worker.graph import route_event


@pytest.mark.asyncio
async def test_3b_load_question_found(base_load_state: dict) -> None:
    get_customer_profiles()
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
    assert "create_task" not in tools
    sms = next(tc for tc in decision.tool_calls if tc.tool == "send_sms")
    assert "456 Delivery St" in sms.arguments["message"]


@pytest.mark.asyncio
async def test_3c_load_question_missing(base_load_state: dict) -> None:
    get_customer_profiles()
    state = copy.deepcopy(base_load_state)
    state["customer_id"] = "customer_b"
    state["load_data"]["stops"][1]["reference_numbers"]["receiver_phone"] = None
    event = {
        "event_id": "evt-3c",
        "event_type": "inbound_communication",
        "inbound_communication": {
            "channel": "sms",
            "sender_type": "driver",
            "content": "Can you send receiver phone number?",
            "attachments": [],
        },
    }
    decision = await route_event(state, event)
    tools = [tc.tool for tc in decision.tool_calls]
    assert "send_sms" in tools
    assert "create_task" in tools
    assert "send_slack_message" in tools
    sms = next(tc for tc in decision.tool_calls if tc.tool == "send_sms")
    assert "checking" in sms.arguments["message"].lower()
    task = next(tc for tc in decision.tool_calls if tc.tool == "create_task")
    assert task.arguments["task_type"] == "missing_load_info"
    slack = next(tc for tc in decision.tool_calls if tc.tool == "send_slack_message")
    assert slack.arguments["audience"] == "broker"


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
