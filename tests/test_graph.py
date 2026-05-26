"""LangGraph unit tests with in-memory checkpointer and a scripted chat model."""

from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import MemorySaver

from app.worker import agent as agent_module
from app.worker.graph import build_graph, graph_config, invoke_input, query_load_state

from tests._llm_stub import ScriptedChatModel, tool_call


@pytest.mark.asyncio
async def test_graph_processes_inbound_event(monkeypatch: pytest.MonkeyPatch) -> None:
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
                            "message": "456 Delivery St, Dallas, TX 75201",
                        },
                    ),
                ],
            ),
            AIMessage(
                content=(
                    "SUMMARY: Replied to driver with delivery address by SMS.\n"
                    "RATIONALE: Driver asked for delivery address; value was in load_data."
                ),
            ),
        ]
    )
    monkeypatch.setattr(agent_module, "get_chat_model", lambda: scripted)

    checkpointer = MemorySaver()
    graph = build_graph(checkpointer)
    load_id = "graph-test-3b"
    seed = {
        "customer_id": "customer_a",
        "milestone": "on_route_to_delivery",
        "load_data": {
            "external_load_id": "FH-1",
            "companies": {
                "broker": {"name": "B"},
                "shipper": {"name": "S"},
                "carrier": {"name": "C"},
            },
            "stops": [
                {
                    "stop_id": "d1",
                    "type": "delivery",
                    "address": {
                        "line_1": "456 Delivery St",
                        "city": "Dallas",
                        "state": "TX",
                        "postal_code": "75201",
                        "country": "US",
                    },
                    "appointment": {"type": "fixed", "timezone": "America/Chicago"},
                    "coordinates": {"lat": 32.0, "lng": -96.0},
                    "reference_numbers": {},
                }
            ],
        },
    }

    await graph.ainvoke(invoke_input(load_id, "seed", seed), graph_config(load_id))
    await graph.ainvoke(
        invoke_input(
            load_id,
            "event",
            {
                "event_id": "evt-wf",
                "event_type": "inbound_communication",
                "load_id": load_id,
                "customer_id": "customer_a",
                "occurred_at": "2026-05-11T17:05:00Z",
                "inbound_communication": {
                    "channel": "sms",
                    "sender_type": "driver",
                    "content": "What's the delivery address?",
                    "attachments": [],
                },
            },
        ),
        graph_config(load_id),
    )

    state = await query_load_state(checkpointer, load_id)
    tools = [tc["tool"] for tc in state["tool_calls"]]
    assert "send_sms" in tools


@pytest.mark.asyncio
async def test_graph_tracking_three_pings_transitions_to_at_delivery() -> None:
    checkpointer = MemorySaver()
    graph = build_graph(checkpointer)
    load_id = "graph-test-3h"
    seed = {
        "customer_id": "customer_b",
        "milestone": "on_route_to_delivery",
        "load_data": {
            "external_load_id": "FH-2",
            "companies": {
                "broker": {"name": "B"},
                "shipper": {"name": "S"},
                "carrier": {"name": "C"},
            },
            "stops": [],
        },
    }
    await graph.ainvoke(invoke_input(load_id, "seed", seed), graph_config(load_id))

    for i in range(1, 4):
        ping = {
            "event_id": f"trk-{i}",
            "event_type": "tracking",
            "load_id": load_id,
            "customer_id": "customer_b",
            "occurred_at": f"2026-05-11T17:3{i}:00Z",
            "tracking": {
                "tracking_id": f"trk-{i}",
                "lat": 32.777,
                "lng": -96.797,
                "distance_to_delivery_miles": 0.2,
                "ping_sequence": i,
                "provider": "mock",
            },
        }
        await graph.ainvoke(invoke_input(load_id, "event", ping), graph_config(load_id))

    state = await query_load_state(checkpointer, load_id)
    assert state["milestone"] == "at_delivery"
    tools = [tc["tool"] for tc in state["tool_calls"]]
    assert "update_load_state" in tools
    assert "cancel_timers" in tools
