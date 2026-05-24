"""LangGraph unit tests with in-memory checkpointer."""

from __future__ import annotations

import pytest
from langgraph.checkpoint.memory import MemorySaver

from app.worker.graph import build_graph, graph_config, invoke_input, query_load_state


@pytest.mark.asyncio
async def test_graph_processes_inbound_event() -> None:
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
