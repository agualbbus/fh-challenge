"""LangGraph wiring for per-load processing.

Public surface — what every importer in the repo depends on:

- `process_work_message`  : SQS handler entry point
- `build_graph`           : compile graph against a checkpointer
- `graph_config`,
  `invoke_input`,
  `thread_id_for_load`    : graph addressing helpers
- `query_load_state`      : checkpoint reader used by the eval harness
- `route_event`           : pure event dispatcher (used by router tests)
"""

from __future__ import annotations

import logging
from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph


from app.queue.messages import WorkMessage
from app.worker.agent import route_event
from app.worker.nodes import (
    KIND_TO_NODE,
    event_node,
    seed_node,
    select_branch,
    task_node,
    timer_node,
)
from app.worker.state import LoadGraphState

logger = logging.getLogger(__name__)

__all__ = [
    "build_graph",
    "graph_config",
    "invoke_input",
    "process_work_message",
    "query_load_state",
    "route_event",
    "thread_id_for_load",
]


def build_graph(checkpointer: BaseCheckpointSaver):
    builder = StateGraph(LoadGraphState)
    builder.add_node("seed", seed_node)
    builder.add_node("task", task_node)
    builder.add_node("timer", timer_node)
    builder.add_node("event", event_node)
    builder.add_conditional_edges(START, select_branch, list(KIND_TO_NODE.values()))
    for node in KIND_TO_NODE.values():
        builder.add_edge(node, END)
    return builder.compile(checkpointer=checkpointer)


def thread_id_for_load(load_id: str) -> str:
    return f"load-{load_id}"


def graph_config(load_id: str) -> dict[str, Any]:
    return {"configurable": {"thread_id": thread_id_for_load(load_id)}}


def invoke_input(load_id: str, kind: str, payload: dict[str, Any]) -> LoadGraphState:
    return {"load_id": load_id, "kind": kind, "payload": payload}


def _trace_config_for_message(message: WorkMessage) -> dict[str, Any]:
    """Per-invocation LangSmith config: descriptive root name + filterable tags/metadata."""
    payload = message.payload or {}
    event_type = payload.get("event_type") if message.kind == "event" else None
    inbound = payload.get("inbound_communication") or {} if message.kind == "event" else {}
    detail = event_type or payload.get("task_instruction_type") or payload.get("timer_type") or ""
    run_name = f"watchtower.{message.kind}" + (f".{detail}" if detail else "")

    tags = [f"kind:{message.kind}", f"load:{message.load_id}"]
    if event_type:
        tags.append(f"event_type:{event_type}")
    if channel := inbound.get("channel"):
        tags.append(f"channel:{channel}")
    if sender := inbound.get("sender_type"):
        tags.append(f"sender:{sender}")

    metadata: dict[str, Any] = {
        "load_id": message.load_id,
        "kind": message.kind,
        "dedup_id": message.dedup_id,
    }
    if event_type:
        metadata["event_type"] = event_type
        metadata["event_id"] = payload.get("event_id")
    if inbound:
        metadata["channel"] = inbound.get("channel")
        metadata["sender_type"] = inbound.get("sender_type")

    return {
        "configurable": {"thread_id": thread_id_for_load(message.load_id)},
        "run_name": run_name,
        "tags": tags,
        "metadata": {k: v for k, v in metadata.items() if v is not None},
    }


async def process_work_message(checkpointer: BaseCheckpointSaver, message: WorkMessage) -> None:
    graph = build_graph(checkpointer)
    logger.info(
        "Processing work message load_id=%s kind=%s dedup_id=%s",
        message.load_id,
        message.kind,
        message.dedup_id,
    )
    try:
        await graph.ainvoke(
            invoke_input(message.load_id, message.kind, message.payload),
            _trace_config_for_message(message),
            durability="sync",
        )
    except Exception:
        logger.exception(
            "Graph invocation failed load_id=%s kind=%s",
            message.load_id,
            message.kind,
        )
        raise


async def query_load_state(checkpointer: BaseCheckpointSaver, load_id: str) -> dict[str, Any]:
    """Read checkpointed state for eval assertions."""
    graph = build_graph(checkpointer)
    snap = await graph.aget_state(graph_config(load_id))
    values = snap.values if snap else {}
    load_state = values.get("load_state") or {}
    return {
        "load_state": load_state,
        "session": values.get("session") or {},
        "tool_calls": values.get("tool_calls") or [],
        "active_timers": values.get("active_timers") or {},
        "milestone": load_state.get("milestone"),
    }
