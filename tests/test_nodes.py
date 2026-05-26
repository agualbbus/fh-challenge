"""Worker graph node logic in isolation."""

from __future__ import annotations

import pytest

from app.worker import nodes


def test_select_branch_known_kinds() -> None:
    assert nodes.select_branch({"kind": "seed"}) == "seed"
    assert nodes.select_branch({"kind": "task"}) == "task"
    assert nodes.select_branch({"kind": "timer"}) == "timer"
    assert nodes.select_branch({"kind": "event"}) == "event"


def test_select_branch_unknown_falls_back_to_event() -> None:
    assert nodes.select_branch({}) == "event"
    assert nodes.select_branch({"kind": "weird"}) == "event"


def test_seed_node_sets_active_task_from_milestone() -> None:
    state = {
        "load_id": "L1",
        "payload": {
            "customer_id": "customer_a",
            "milestone": "at_delivery",
            "load_data": {},
        },
    }
    out = nodes.seed_node(state)
    assert out["load_state"]["active_task"] == "confirm_delivery"
    assert out["load_state"]["load_id"] == "L1"


def test_seed_node_respects_explicit_active_task() -> None:
    state = {
        "load_id": "L1",
        "payload": {
            "customer_id": "customer_a",
            "milestone": "at_delivery",
            "active_task": "delivery_eta_checkpoint",
        },
    }
    out = nodes.seed_node(state)
    assert out["load_state"]["active_task"] == "delivery_eta_checkpoint"


def test_task_node_no_op_when_missing_type() -> None:
    assert nodes.task_node({"payload": {}}) == {}


def test_task_node_updates_active_task() -> None:
    out = nodes.task_node(
        {
            "load_id": "L1",
            "load_state": {
                "load_id": "L1",
                "customer_id": "c",
                "milestone": "on_route_to_delivery",
                "load_data": {},
                "active_task": "delivery_eta_checkpoint",
            },
            "payload": {"task_instruction_type": "confirm_delivery"},
        }
    )
    assert out["load_state"]["active_task"] == "confirm_delivery"


def test_task_node_initializes_load_state_when_missing() -> None:
    out = nodes.task_node(
        {"load_id": "L9", "payload": {"task_instruction_type": "confirm_delivery"}}
    )
    assert out["load_state"]["load_id"] == "L9"
    assert out["load_state"]["active_task"] == "confirm_delivery"


def test_timer_node_returns_empty() -> None:
    assert nodes.timer_node({}) == {}


@pytest.mark.asyncio
async def test_event_node_guards_unseeded_load() -> None:
    out = await nodes.event_node(
        {
            "load_id": "L1",
            "payload": {"event_id": "e1", "event_type": "inbound_communication"},
        }
    )
    assert out["tool_calls"] == []
    assert out["messages"] == []


@pytest.mark.asyncio
async def test_event_node_tracking_accumulates_pings_below_threshold() -> None:
    state = {
        "load_id": "L1",
        "load_state": {
            "load_id": "L1",
            "customer_id": "customer_b",
            "milestone": "on_route_to_delivery",
            "active_task": "delivery_eta_checkpoint",
            "load_data": {},
        },
        "payload": {
            "event_id": "t1",
            "event_type": "tracking",
            "tracking": {"distance_to_delivery_miles": 0.2},
        },
        "session": {},
    }
    out = await nodes.event_node(state)
    assert out["tool_calls"] == []
    assert out["session"]["consecutive_geofence_pings"] == 1


@pytest.mark.asyncio
async def test_event_node_tracking_transitions_on_third_ping() -> None:
    state = {
        "load_id": "L1",
        "load_state": {
            "load_id": "L1",
            "customer_id": "customer_b",
            "milestone": "on_route_to_delivery",
            "active_task": "delivery_eta_checkpoint",
            "load_data": {},
        },
        "payload": {
            "event_id": "t3",
            "event_type": "tracking",
            "tracking": {"distance_to_delivery_miles": 0.1},
        },
        "session": {"consecutive_geofence_pings": 2},
    }
    out = await nodes.event_node(state)
    tools = [tc["tool"] for tc in out["tool_calls"]]
    assert "update_load_state" in tools
    assert "cancel_timers" in tools
    assert out["load_state"]["milestone"] == "at_delivery"
    assert out["active_timers"] == {}


@pytest.mark.asyncio
async def test_event_node_tracking_resets_counter_outside_geofence() -> None:
    state = {
        "load_id": "L1",
        "load_state": {
            "load_id": "L1",
            "customer_id": "customer_b",
            "milestone": "on_route_to_delivery",
            "active_task": "delivery_eta_checkpoint",
            "load_data": {},
        },
        "payload": {
            "event_id": "t2",
            "event_type": "tracking",
            "tracking": {"distance_to_delivery_miles": 5.0},
        },
        "session": {"consecutive_geofence_pings": 2},
    }
    out = await nodes.event_node(state)
    assert out["tool_calls"] == []
    assert out["session"]["consecutive_geofence_pings"] == 0


@pytest.mark.asyncio
async def test_event_node_switches_sop_for_attachment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Attachment on ETA SOP triggers active_task switch to confirm_delivery before agent."""
    captured_task: list[str] = []

    async def fake_invoke(load_state, active_timers, event):  # noqa: ANN001
        captured_task.append(load_state.get("active_task", ""))
        return {
            "state_delta": {},
            "active_timers": None,
            "tool_calls": [],
            "messages": [],
        }

    monkeypatch.setattr(nodes, "_invoke_agent", fake_invoke)

    state = {
        "load_id": "L1",
        "load_state": {
            "load_id": "L1",
            "customer_id": "customer_c",
            "milestone": "on_route_to_delivery",
            "active_task": "delivery_eta_checkpoint",
            "load_data": {},
        },
        "payload": {
            "event_id": "e1",
            "event_type": "inbound_communication",
            "inbound_communication": {
                "channel": "sms",
                "sender_type": "driver",
                "content": "POD attached",
                "attachments": [{"attachment_id": "att-1"}],
            },
        },
    }
    await nodes.event_node(state)
    assert captured_task == ["confirm_delivery"]
