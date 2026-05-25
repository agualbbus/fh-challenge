"""Covers process_work_message + query_load_state with MemorySaver."""

from __future__ import annotations

import pytest
from langgraph.checkpoint.memory import MemorySaver

from app.queue.messages import WorkMessage
from app.worker.graph import (
    graph_config,
    invoke_input,
    process_work_message,
    query_load_state,
    thread_id_for_load,
)


def test_addressing_helpers() -> None:
    assert thread_id_for_load("X") == "load-X"
    assert graph_config("X") == {"configurable": {"thread_id": "load-X"}}
    payload = {"customer_id": "customer_a", "load_data": {}}
    assert invoke_input("X", "seed", payload) == {
        "load_id": "X",
        "kind": "seed",
        "payload": payload,
    }


@pytest.mark.asyncio
async def test_process_work_message_runs_seed_and_checkpoints() -> None:
    checkpointer = MemorySaver()
    msg = WorkMessage(
        load_id="L-pm",
        kind="seed",
        payload={"customer_id": "customer_a", "milestone": "on_route_to_delivery", "load_data": {}},
        dedup_id="seed-L-pm",
    )
    await process_work_message(checkpointer, msg)
    state = await query_load_state(checkpointer, "L-pm")
    assert state["load_state"]["customer_id"] == "customer_a"
    assert state["load_state"]["active_task"] == "delivery_eta_checkpoint"


@pytest.mark.asyncio
async def test_process_work_message_reraises_on_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    checkpointer = MemorySaver()
    msg = WorkMessage(load_id="L-bad", kind="seed", payload={}, dedup_id="d")

    class BoomGraph:
        async def ainvoke(self, *_a, **_kw):
            raise RuntimeError("graph fail")

    monkeypatch.setattr("app.worker.graph.build_graph", lambda _c: BoomGraph())
    with pytest.raises(RuntimeError, match="graph fail"):
        await process_work_message(checkpointer, msg)


@pytest.mark.asyncio
async def test_query_load_state_empty_for_unknown_thread() -> None:
    checkpointer = MemorySaver()
    state = await query_load_state(checkpointer, "missing")
    assert state["load_state"] == {}
    assert state["tool_calls"] == []
