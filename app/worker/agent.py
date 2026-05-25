"""LangChain `create_agent` factory, dynamic SOP prompt, and per-event invocation."""

from __future__ import annotations

import json
import re
from typing import Any

from langchain.agents import AgentState, create_agent
from langchain.agents.middleware import dynamic_prompt
from langchain_core.messages import AIMessage, HumanMessage

from app.customers.base import CustomerProfile, get_customer_profile
from app.models.decision import AgentDecision
from app.tools.context import current_event_var, load_state_var
from app.tools.tools import ALL_TOOLS
from app.worker.llm import get_chat_model
from app.worker.sops import get_sop_document
from app.worker.tool_extraction import extract_tool_records

_SOP_BRANCH_RE = re.compile(r"SOP_BRANCH:\s*([A-Za-z0-9_\-]+)")


class WatchtowerAgentState(AgentState, total=False):
    load_state: dict[str, Any]
    active_timers: dict[str, dict[str, Any]]
    current_event: dict[str, Any]


def _intro() -> str:
    return (
        "You are FreightHero Watchtower, an AI agent for freight load operations.\n"
        "Use the SOP below to pick the correct branch for the incoming event and act with tools."
    )


def _routing_rules() -> str:
    return (
        "Routing rules:\n"
        "- Read the SOP's Event Routing section first and select the single branch that fits the event.\n"
        "- Apply the customer profile expectations that are relevant to that branch only.\n"
        "- Do not invent missing load information. Keep driver-facing messages short and operational.\n"
        "- Match the inbound channel for driver-facing replies unless the customer workflow says otherwise.\n"
        "- Do not call tools that the chosen branch does not authorize."
    )


def _header_block(customer_id: str, task: str, milestone: str) -> str:
    return (
        f"Customer: {customer_id}\n"
        f"Active task: {task}\n"
        f"Milestone: {milestone}"
    )


def _customer_block(profile: CustomerProfile) -> str:
    return f"Customer profile:\n{json.dumps(profile.model_dump(), indent=2)}"


def _sop_block(task: str) -> str:
    sop = get_sop_document(task)
    return f"SOP ({task}):\n{sop or '(no SOP loaded)'}"


def _state_and_event_block(load_state: dict[str, Any], event: dict[str, Any]) -> str:
    return (
        f"Current load state:\n{json.dumps(load_state, indent=2)}\n\n"
        f"Incoming event:\n{json.dumps(event, indent=2)}"
    )


def _output_contract() -> str:
    return (
        "After your tool calls, end your final message with exactly two lines:\n"
        "SOP_BRANCH: <branch_key e.g. operational_issue, load_information_question, "
        "driver_provides_eta, arrival_confirmation, tracking_ping, broker_messages, no_action>\n"
        "RATIONALE: <one short line>"
    )


def build_system_prompt(load_state: dict[str, Any], event: dict[str, Any]) -> str:
    customer_id = load_state.get("customer_id")
    if not customer_id:
        raise ValueError("load_state missing customer_id")
    task = load_state.get("active_task")
    if not task:
        raise ValueError(
            "load_state missing active_task; seed_node should set this from milestone"
        )
    profile = get_customer_profile(customer_id)
    milestone = load_state.get("milestone", "on_route_to_delivery")
    return "\n\n".join(
        [
            _intro(),
            _routing_rules(),
            _header_block(customer_id, task, milestone),
            _customer_block(profile),
            _sop_block(task),
            _state_and_event_block(load_state, event),
            _output_contract(),
        ]
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

    messages = result.get("messages", [])
    tool_calls = extract_tool_records(messages, load_id=load_id, event_id=event_id)
    sop_branch = _extract_sop_branch(messages) or "agent"
    return AgentDecision(
        state_delta=result.get("load_state") or {},
        active_timers=result.get("active_timers"),
        tool_calls=tool_calls,
        noop=not tool_calls,
        reason="agent produced no tool calls" if not tool_calls else "",
        sop_branch=sop_branch,
    )


def _extract_sop_branch(messages: list[Any]) -> str:
    for msg in reversed(messages):
        if not isinstance(msg, AIMessage):
            continue
        match = _SOP_BRANCH_RE.search(msg.text)
        if match:
            return match.group(1)
    return ""


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
