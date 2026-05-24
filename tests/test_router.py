"""Unit tests for agent orchestrator (3b / 3c)."""

from __future__ import annotations

import pytest

from app.worker.graph import route_event
from app.customers.base import get_customer_profiles


def _base_load_state(customer_id: str, load_data: dict) -> dict:
    return {
        "load_id": "load-test",
        "customer_id": customer_id,
        "milestone": "on_route_to_delivery",
        "load_data": load_data,
        "active_task": "delivery_eta_checkpoint",
    }


def _base_load_data(receiver_phone: str | None = "+15555550200") -> dict:
    return {
        "external_load_id": "FH-2026-001",
        "companies": {
            "broker": {"name": "Example Broker"},
            "shipper": {"name": "Example Shipper"},
            "carrier": {"name": "Example Carrier"},
        },
        "contacts": {},
        "stops": [
            {
                "stop_id": "pickup-1",
                "type": "pickup",
                "address": {
                    "line_1": "123 Pickup Ave",
                    "city": "Chicago",
                    "state": "IL",
                    "postal_code": "60601",
                    "country": "US",
                },
                "appointment": {"type": "fixed", "timezone": "America/Chicago"},
                "coordinates": {"lat": 41.0, "lng": -87.0},
                "reference_numbers": {},
            },
            {
                "stop_id": "delivery-1",
                "type": "delivery",
                "address": {
                    "line_1": "456 Delivery St",
                    "line_2": "Dock 4",
                    "city": "Dallas",
                    "state": "TX",
                    "postal_code": "75201",
                    "country": "US",
                },
                "appointment": {"type": "fixed", "timezone": "America/Chicago"},
                "coordinates": {"lat": 32.0, "lng": -96.0},
                "reference_numbers": {"receiver_phone": receiver_phone},
            },
        ],
    }


@pytest.mark.asyncio
async def test_3b_load_question_found() -> None:
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
    state = _base_load_state("customer_a", _base_load_data())
    decision = await route_event(state, event)
    tools = [tc.tool for tc in decision.tool_calls]
    assert "send_sms" in tools
    assert "create_task" not in tools
    sms = next(tc for tc in decision.tool_calls if tc.tool == "send_sms")
    assert "456 Delivery St" in sms.arguments["message"]


@pytest.mark.asyncio
async def test_3c_load_question_missing() -> None:
    get_customer_profiles()
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
    state = _base_load_state("customer_b", _base_load_data(receiver_phone=None))
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
async def test_broker_ignore() -> None:
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
    state = _base_load_state("customer_a", _base_load_data())
    decision = await route_event(state, event)
    assert decision.noop is True
    assert len(decision.tool_calls) == 0
