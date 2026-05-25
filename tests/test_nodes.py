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
