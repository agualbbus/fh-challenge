"""LangChain `create_agent` factory, dynamic SOP prompt, and per-event invocation."""

from __future__ import annotations

import json
from typing import Any

from langchain.agents import AgentState, create_agent
from langchain.agents.middleware import dynamic_prompt
from langchain_core.messages import HumanMessage

from app.customers.base import get_customer_profile
from app.models.decision import AgentDecision
from app.tools.context import current_event_var, load_state_var
from app.tools.tools import ALL_TOOLS
from app.worker.llm import get_chat_model
from app.worker.sops import get_sop_section
from app.worker.tool_extraction import extract_tool_records


class WatchtowerAgentState(AgentState, total=False):
    load_state: dict[str, Any]
    active_timers: dict[str, dict[str, Any]]
    current_event: dict[str, Any]


def build_system_prompt(load_state: dict[str, Any], event: dict[str, Any]) -> str:
    customer_id = load_state.get("customer_id")
    if not customer_id:
        raise ValueError("load_state missing customer_id")
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
    return build_system_prompt(
        request.state.get("load_state") or {},
        request.state.get("current_event") or {},
    )


def build_agent():
    return create_agent(
        get_chat_model(),
        tools=ALL_TOOLS,
        middleware=[sop_prompt],
        state_schema=WatchtowerAgentState,
    )


async def run_agent_for_event(
    load_state: dict[str, Any],
    active_timers: dict[str, dict[str, Any]],
    event: dict[str, Any],
) -> AgentDecision:
    """Invoke the agent for one event; ContextVars feed mock LLM + stateful tools."""
    load_id = load_state.get("load_id", "unknown")
    event_id = event.get("event_id", "unknown")

    load_token = load_state_var.set(load_state)
    event_token = current_event_var.set(event)
    try:
        agent = build_agent()
        result = await agent.ainvoke(
            {
                "messages": [HumanMessage(content=json.dumps(event))],
                "load_state": load_state,
                "active_timers": active_timers,
                "current_event": event,
            },
        )
    finally:
        load_state_var.reset(load_token)
        current_event_var.reset(event_token)

    tool_calls = extract_tool_records(
        result.get("messages", []), load_id=load_id, event_id=event_id
    )
    return AgentDecision(
        state_delta=result.get("load_state") or {},
        active_timers=result.get("active_timers"),
        tool_calls=tool_calls,
        noop=not tool_calls,
        reason="agent produced no tool calls" if not tool_calls else "",
        sop_branch="agent",
    )


async def route_event(
    load_state: dict[str, Any],
    event: dict[str, Any],
    active_timers: dict[str, dict[str, Any]] | None = None,
) -> AgentDecision:
    """Top-level event dispatcher. Broker messages short-circuit; everything else hits the agent."""
    if event.get("event_type") == "inbound_communication":
        if event.get("inbound_communication", {}).get("sender_type") == "broker":
            return AgentDecision(
                noop=True, reason="broker message ignored", sop_branch="broker_messages"
            )
        return await run_agent_for_event(load_state, active_timers or {}, event)
    return AgentDecision(noop=True, reason="no matching branch", sop_branch="no_action")
