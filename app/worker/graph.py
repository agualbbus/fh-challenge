"""LangGraph per-load worker flow."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from langchain.agents import create_agent
from langchain.agents.middleware import dynamic_prompt
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.func import task
from langgraph.graph import END, START, StateGraph

from app.customers.base import get_customer_profile
from app.models.decision import AgentDecision, ToolCallRecord
from app.queue.messages import WorkMessage
from app.queue.publisher import schedule_timer_message
from app.tools.context import current_event_var, load_state_var
from app.tools.tools import ALL_TOOLS
from app.worker.llm import get_chat_model
from app.worker.sops import get_sop_section
from app.worker.state import LoadGraphState


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _build_system_prompt(load_state: dict[str, Any], event: dict[str, Any]) -> str:
    customer_id = load_state.get("customer_id", "customer_a")
    profile = get_customer_profile(customer_id)
    task = load_state.get("active_task") or "delivery_eta_checkpoint"
    sop = get_sop_section(task, "load_information_question")
    return (
        "You are FreightHero Watchtower, an AI agent for freight load operations.\n"
        "Follow the SOP and use tools to respond to events. Call tools as needed.\n\n"
        f"Customer: {customer_id}\n"
        f"Active task: {task}\n"
        f"Milestone: {load_state.get('milestone', 'on_route_to_delivery')}\n"
        f"Missing load info policy: create_task={profile.missing_load_info.create_task}, "
        f"notify_slack={profile.missing_load_info.notify_slack}\n\n"
        f"SOP section:\n{sop or '(no section loaded)'}\n"
        f"\nCurrent load state:\n{json.dumps(load_state, indent=2)}\n"
        f"\nIncoming event:\n{json.dumps(event, indent=2)}"
    )


@dynamic_prompt
def sop_prompt(request) -> str:  # noqa: ANN001
    load_state = load_state_var.get()
    event = current_event_var.get()
    return _build_system_prompt(load_state, event)


def get_agent():
    """Build a create_agent instance backed by ChatOpenRouter or mock LLM."""
    return create_agent(
        get_chat_model(),
        tools=ALL_TOOLS,
        middleware=[sop_prompt],
    )


def _extract_tool_records(
    messages: list[Any],
    *,
    load_id: str,
    event_id: str,
) -> list[ToolCallRecord]:
    records: list[ToolCallRecord] = []
    pending: dict[str, dict[str, Any]] = {}

    for msg in messages:
        if isinstance(msg, AIMessage) and msg.tool_calls:
            for tc in msg.tool_calls:
                tc_id = tc.get("id", str(uuid.uuid4()))
                pending[tc_id] = {
                    "name": tc.get("name", ""),
                    "args": tc.get("args", {}),
                }
        elif isinstance(msg, ToolMessage):
            tc_id = msg.tool_call_id
            info = pending.pop(tc_id, {})
            result = msg.content
            if isinstance(result, str):
                try:
                    result = json.loads(result)
                except json.JSONDecodeError:
                    result = {"result": result}
            if not isinstance(result, dict):
                result = {"result": result}
            records.append(
                ToolCallRecord(
                    tool_call_id=tc_id,
                    event_id=event_id,
                    load_id=load_id,
                    tool=info.get("name", ""),
                    arguments=info.get("args", {}),
                    result=result,
                    created_at=_now_iso(),
                )
            )
    return records


async def run_agent_for_event(
    load_state: dict[str, Any],
    event: dict[str, Any],
) -> AgentDecision:
    load_id = load_state.get("load_id", "unknown")
    event_id = event.get("event_id", "unknown")
    load_state = {**load_state, "_current_event": event}

    load_token = load_state_var.set(load_state)
    event_token = current_event_var.set(event)
    try:
        agent = get_agent()
        result = await agent.ainvoke(
            {"messages": [HumanMessage(content=json.dumps(event))]},
        )
        tool_calls = _extract_tool_records(
            result.get("messages", []),
            load_id=load_id,
            event_id=event_id,
        )
        sop_branch = "agent"
        if not tool_calls:
            return AgentDecision(
                noop=True,
                reason="agent produced no tool calls",
                sop_branch=sop_branch,
            )
        return AgentDecision(tool_calls=tool_calls, sop_branch=sop_branch)
    finally:
        load_state_var.reset(load_token)
        current_event_var.reset(event_token)


def _sender_type(event: dict[str, Any]) -> str | None:
    if event.get("event_type") != "inbound_communication":
        return None
    return event.get("inbound_communication", {}).get("sender_type")


def _handle_broker() -> AgentDecision:
    return AgentDecision(
        noop=True,
        reason="broker message ignored",
        sop_branch="broker_messages",
    )


async def route_event(
    load_state: dict[str, Any],
    event: dict[str, Any],
) -> AgentDecision:
    sender = _sender_type(event)
    if sender == "broker":
        return _handle_broker()

    if event.get("event_type") == "inbound_communication":
        return await run_agent_for_event(load_state, event)

    return AgentDecision(noop=True, reason="no matching branch", sop_branch="no_action")


async def route_work_item(
    load_state: dict[str, Any],
    work_kind: str,
    payload: dict[str, Any],
) -> AgentDecision:
    if work_kind == "task":
        task_type = payload.get("task_instruction_type")
        if task_type:
            return AgentDecision(
                state_delta={"active_task": task_type},
                sop_branch="task_submitted",
            )
        return AgentDecision(noop=True, reason="empty task", sop_branch="task_submitted")

    if work_kind == "timer":
        timer_type = payload.get("timer_type", "eta_followup")
        return AgentDecision(
            noop=True,
            reason=f"timer fired: {timer_type}",
            sop_branch="timer_fired",
        )

    return await route_event(load_state, payload)


@task
async def _run_agent_task(
    load_state: dict[str, Any],
    work_kind: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Durable task: agent + tools (replay-safe side effects)."""
    decision = await route_work_item(load_state, work_kind, payload)
    return {
        "state_delta": decision.state_delta,
        "tool_calls": [tc.to_dict() for tc in decision.tool_calls],
        "noop": decision.noop,
        "reason": decision.reason,
        "sop_branch": decision.sop_branch,
    }


def _merge_load_data(existing: dict[str, Any], delta: dict[str, Any]) -> dict[str, Any]:
    merged = {**existing}
    for key, value in delta.items():
        if key == "load_data" and isinstance(value, dict):
            merged["load_data"] = {**merged.get("load_data", {}), **value}
        else:
            merged[key] = value
    return merged


def _apply_decision(
    load_state: dict[str, Any],
    active_timers: dict[str, dict[str, Any]],
    decision: dict[str, Any],
    load_id: str,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]], list[dict[str, Any]]]:
    delta = decision.get("state_delta") or {}
    load_state = _merge_load_data(load_state, delta)

    new_tool_calls: list[dict[str, Any]] = list(decision.get("tool_calls", []))
    for tc in new_tool_calls:
        if tc.get("tool") == "update_load_state":
            new_state = tc.get("result", {}).get("new_state")
            if new_state:
                load_state["milestone"] = new_state

        if tc.get("tool") == "create_timer":
            args = tc.get("arguments", {})
            result = tc.get("result", {})
            timer_id = result.get("timer_id", args.get("timer_id", ""))
            timer_type = args.get("timer_type", "eta_followup")
            fire_at_utc = args.get("fire_at_utc", "")
            if timer_id:
                active_timers[timer_id] = {
                    "timer_id": timer_id,
                    "timer_type": timer_type,
                    "fire_at_utc": fire_at_utc,
                }
                schedule_timer_message(
                    load_id=load_id,
                    timer_id=timer_id,
                    timer_type=timer_type,
                    fire_at_utc=fire_at_utc,
                )

        elif tc.get("tool") == "cancel_timer":
            timer_id = tc.get("arguments", {}).get("timer_id", "")
            active_timers.pop(timer_id, None)

        elif tc.get("tool") == "cancel_timers":
            timer_type = tc.get("arguments", {}).get("timer_type")
            if timer_type is None:
                active_timers.clear()
            else:
                active_timers = {
                    k: v
                    for k, v in active_timers.items()
                    if v.get("timer_type") != timer_type
                }

    return load_state, active_timers, new_tool_calls


def _init_load_state(load_id: str, seed: dict[str, Any]) -> dict[str, Any]:
    return {
        "load_id": load_id,
        "customer_id": seed.get("customer_id"),
        "milestone": seed.get("milestone", "on_route_to_delivery"),
        "load_data": seed.get("load_data", {}),
        "active_task": seed.get("active_task"),
    }


async def process_work_item(state: LoadGraphState) -> LoadGraphState:
    load_id = state.get("load_id", "")
    kind = state.get("kind", "")
    payload = state.get("payload") or {}

    load_state = dict(state.get("load_state") or {})
    session = dict(state.get("session") or {})
    active_timers = dict(state.get("active_timers") or {})

    if kind == "seed":
        load_state = _init_load_state(load_id, payload)
        return {
            "load_state": load_state,
            "session": session,
            "active_timers": active_timers,
            "tool_calls": [],
        }

    if not load_state:
        load_state = _init_load_state(load_id, {})

    decision = await _run_agent_task(load_state, kind, payload)

    load_state, active_timers, new_tool_calls = _apply_decision(
        load_state, active_timers, decision, load_id
    )

    return {
        "load_state": load_state,
        "session": session,
        "active_timers": active_timers,
        "tool_calls": new_tool_calls,
    }


def build_graph(checkpointer: BaseCheckpointSaver):
    builder = StateGraph(LoadGraphState)
    builder.add_node("process", process_work_item)
    builder.add_edge(START, "process")
    builder.add_edge("process", END)
    return builder.compile(checkpointer=checkpointer)


def thread_id_for_load(load_id: str) -> str:
    return f"load-{load_id}"


def graph_config(load_id: str) -> dict[str, Any]:
    return {"configurable": {"thread_id": thread_id_for_load(load_id)}}


def invoke_input(load_id: str, kind: str, payload: dict[str, Any]) -> LoadGraphState:
    return {
        "load_id": load_id,
        "kind": kind,
        "payload": payload,
    }


async def process_work_message(
    checkpointer: BaseCheckpointSaver,
    message: WorkMessage,
) -> None:
    graph = build_graph(checkpointer)
    await graph.ainvoke(
        invoke_input(message.load_id, message.kind, message.payload),
        graph_config(message.load_id),
        durability="sync",
    )


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
