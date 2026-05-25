"""Graph nodes — one per work kind. Routing is explicit via `Command`."""

from __future__ import annotations

import logging
from typing import Any

from langgraph.func import task

from app.models.decision import AgentDecision
from app.worker.agent import route_event
from app.worker.merge import init_load_state, merge_load_data
from app.worker.sops import task_for_milestone
from app.worker.state import LoadGraphState

logger = logging.getLogger(__name__)

KIND_TO_NODE = {"seed": "seed", "task": "task", "timer": "timer", "event": "event"}


def select_branch(state: LoadGraphState) -> str:
    """Conditional edge from START: dispatch on `kind`; unknown → event."""
    return KIND_TO_NODE.get(state.get("kind", ""), "event")


def seed_node(state: LoadGraphState) -> dict[str, Any]:
    payload = dict(state.get("payload") or {})
    if "active_task" not in payload:
        payload["active_task"] = task_for_milestone(payload.get("milestone"))
    return {"load_state": init_load_state(state.get("load_id", ""), payload)}


def task_node(state: LoadGraphState) -> dict[str, Any]:
    task_type = (state.get("payload") or {}).get("task_instruction_type")
    if not task_type:
        return {}
    existing = state.get("load_state") or init_load_state(state.get("load_id", ""), {})
    return {"load_state": merge_load_data(existing, {"active_task": task_type})}


def timer_node(state: LoadGraphState) -> dict[str, Any]:
    # Phase 4+ will dispatch by timer_type. Until then, firing is observed via checkpoint only.
    return {}


@task
async def _invoke_agent(
    load_state: dict[str, Any],
    active_timers: dict[str, dict[str, Any]],
    event: dict[str, Any],
) -> dict[str, Any]:
    """Durable wrapper around the LLM + tool side effects."""
    decision = await route_event(load_state, event, active_timers)
    return {
        "state_delta": decision.state_delta,
        "active_timers": decision.active_timers,
        "tool_calls": [tc.to_dict() for tc in decision.tool_calls],
        "messages": decision.messages,
    }


async def event_node(state: LoadGraphState) -> dict[str, Any]:
    event = state.get("payload") or {}
    load_state = state.get("load_state") or init_load_state(state.get("load_id", ""), {})
    active_timers = dict(state.get("active_timers") or {})

    # Guard against events arriving before the load has been seeded. Without
    # this, build_system_prompt raises ValueError and the message bounces
    # through SQS retries forever.
    if not load_state.get("customer_id") or not load_state.get("active_task"):
        logger.warning(
            "Skipping event for unseeded load load_id=%s event_id=%s",
            state.get("load_id"),
            event.get("event_id"),
        )
        decision = AgentDecision(
            noop=True,
            reason="load_state not initialized; event arrived before seed",
            summary="No action.",
            rationale="missing customer_id or active_task",
        )
        return {
            "tool_calls": [tc.to_dict() for tc in decision.tool_calls],
            "messages": decision.messages,
        }

    result = await _invoke_agent(load_state, active_timers, event)

    update: dict[str, Any] = {
        "load_state": merge_load_data(load_state, result["state_delta"]),
        "tool_calls": result["tool_calls"],
        "messages": result["messages"],
    }
    if result["active_timers"] is not None:
        update["active_timers"] = result["active_timers"]
    return update
