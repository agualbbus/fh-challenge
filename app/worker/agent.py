"""LangChain `create_agent` factory, dynamic SOP prompt, and per-event invocation."""

from __future__ import annotations

import json
import logging
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

logger = logging.getLogger(__name__)

# Plain-text final-answer markers. We avoid `response_format=` because binding
# a Pydantic schema makes the model skip the tool loop on most providers.
_SUMMARY_RE = re.compile(r"^\s*SUMMARY\s*:\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE)
_RATIONALE_RE = re.compile(r"^\s*RATIONALE\s*:\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE)


def _message_text(msg: Any) -> str:
    content = getattr(msg, "content", "")
    if isinstance(content, str):
        return content
    # Some providers (e.g. Anthropic) return a list of content blocks.
    parts: list[str] = []
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict):
                text = block.get("text")
                if isinstance(text, str):
                    parts.append(text)
            elif isinstance(block, str):
                parts.append(block)
    return "\n".join(parts)


def parse_final_answer(messages: list[Any]) -> tuple[str, str]:
    """Pull `SUMMARY:` and `RATIONALE:` from the last AIMessage text content."""
    for msg in reversed(messages):
        if not isinstance(msg, AIMessage):
            continue
        text = _message_text(msg)
        if not text:
            continue
        summary_match = _SUMMARY_RE.search(text)
        rationale_match = _RATIONALE_RE.search(text)
        if summary_match or rationale_match:
            return (
                summary_match.group(1).strip() if summary_match else "",
                rationale_match.group(1).strip() if rationale_match else "",
            )
    return "", ""


class WatchtowerAgentState(AgentState, total=False):
    load_state: dict[str, Any]
    active_timers: dict[str, dict[str, Any]]
    current_event: dict[str, Any]


def _role_block() -> str:
    return (
        "<role>\n"
        "You are FreightHero Watchtower, an AI agent for freight load operations.\n"
        "Use the SOP below to pick the correct section for the incoming event and act with tools.\n"
        "</role>"
    )


def _routing_rules_block() -> str:
    return (
        "<routing_rules>\n"
        "- Read the SOP's Event Routing section first and select the single section that fits the event.\n"
        "- Apply the customer profile expectations that are relevant to that section only.\n"
        "- Do not invent missing load information. Keep driver-facing messages short and operational.\n"
        "- Match the inbound channel for driver-facing replies unless the customer workflow says otherwise.\n"
        "- Do not call tools that the chosen section does not authorize.\n"
        "</routing_rules>"
    )


def _context_block(customer_id: str, task: str, milestone: str) -> str:
    return (
        "<context>\n"
        f"- customer_id: {customer_id}\n"
        f"- active_task: {task}\n"
        f"- milestone: {milestone}\n"
        "</context>"
    )


def _format_customer_profile(profile: CustomerProfile) -> str:
    pod = profile.pod
    pod_bits = [f"{pod.validation} validation"]
    if pod.notify_on_received:
        pod_bits.append("notify on received")
    if pod.notify_delivered_without_pod:
        pod_bits.append("notify if delivered without POD")
    pod_line = "; ".join(pod_bits)

    mli = profile.missing_load_info
    mli_bits: list[str] = []
    mli_bits.append("create internal task" if mli.create_task else "do not create task")
    mli_bits.append(
        f"notify Slack (audience: {mli.slack_audience})"
        if mli.notify_slack
        else f"do not notify Slack (audience: {mli.slack_audience})"
    )
    mli_line = "; ".join(mli_bits)

    return (
        f"<customer_profile customer_id=\"{profile.customer_id}\">\n"
        f"- Escalation channels: {', '.join(profile.escalation.channels)}\n"
        f"- Delivery geofence radius: {profile.geofence_radius_miles} miles\n"
        f"- ETA follow-up cadence: every {profile.eta_followup_minutes} minutes\n"
        f"- POD: {pod_line}\n"
        f"- Missing load info: {mli_line}\n"
        f"- Lumper handling: {profile.lumper.mode}\n"
        f"- First arrival message key: {profile.first_arrival_message}\n"
        "</customer_profile>"
    )


def _sop_block(task: str) -> str:
    sop = get_sop_document(task)
    return f"<sop task=\"{task}\">\n{sop or '(no SOP loaded)'}\n</sop>"


def _load_state_block(load_state: dict[str, Any]) -> str:
    return f"<load_state>\n{json.dumps(load_state, indent=2)}\n</load_state>"


def _event_block(event: dict[str, Any]) -> str:
    return f"<incoming_event>\n{json.dumps(event, indent=2)}\n</incoming_event>"


def _examples_block() -> str:
    return (
        "<examples>\n"
        "Example 1 — Driver asks for delivery address (SMS):\n"
        "- Tool call: get_load_info(field=\"delivery_address\")\n"
        "- Tool call: send_sms(recipient=\"driver\", message=\"456 Delivery St, Dallas, TX 75201\")\n"
        "- Final message after tools:\n"
        "  SUMMARY: Replied to driver with delivery address by SMS.\n"
        "  RATIONALE: Driver asked for delivery address; value was in load_data.\n"
        "\n"
        "Example 2 — Driver provides ETA \"ETA 3pm\" (SMS):\n"
        "- Tool call: record_eta(eta=\"15:00\", timezone=\"America/Chicago\")\n"
        "- Tool call: send_sms(recipient=\"driver\", message=\"Got it — ETA 3pm noted.\")\n"
        "- Final message after tools:\n"
        "  SUMMARY: Recorded driver ETA of 15:00 local and acknowledged on SMS.\n"
        "  RATIONALE: Driver provided usable ETA; recorded and acknowledged per SOP.\n"
        "\n"
        "Example 3 — Driver reports breakdown (SMS):\n"
        "- Tool call: create_issue(title=\"Operational issue reported\", description=\"truck broke down\", issue_type=\"equipment_failure\")\n"
        "- Tool call: send_sms(recipient=\"driver\", message=\"Thanks — the team will review this shortly.\")\n"
        "- Final message after tools:\n"
        "  SUMMARY: Logged breakdown as operational issue and acknowledged driver on SMS.\n"
        "  RATIONALE: Driver reported equipment failure; SOP requires logging + brief ack.\n"
        "</examples>"
    )


def _output_contract_block() -> str:
    return (
        "<output_contract>\n"
        "Process the event in two phases:\n"
        "1. CALL TOOLS first. Execute every tool needed to satisfy the SOP for the "
        "selected section (record data, notify channels, create tasks/issues, "
        "manage timers). Do NOT skip the tool phase.\n"
        "2. AFTER all tool calls are complete, return ONE final assistant message "
        "containing exactly two lines and nothing else:\n"
        "   SUMMARY: <one sentence describing what you did this turn>\n"
        "   RATIONALE: <one short line explaining why that fits the SOP>\n"
        "Do not wrap these lines in JSON, code fences, or extra prose. The labels "
        "SUMMARY: and RATIONALE: are parsed by regex downstream.\n"
        "</output_contract>"
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
            _role_block(),
            _routing_rules_block(),
            _context_block(customer_id, task, milestone),
            _format_customer_profile(profile),
            _sop_block(task),
            _load_state_block(load_state),
            _event_block(event),
            _examples_block(),
            _output_contract_block(),
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
    """Invoke the agent for one event; ContextVars feed stateful tools."""
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
    except Exception as exc:
        # Surface a structured failure rather than crashing the graph. SQS
        # will retry on transport errors, but LLM/output-parser failures are
        # often deterministic — recording the error in the checkpoint lets
        # the message be acknowledged and inspected.
        logger.exception(
            "Agent invocation failed load_id=%s event_id=%s",
            load_id,
            event_id,
        )
        return AgentDecision(
            noop=True,
            reason=f"agent invocation error: {type(exc).__name__}: {exc}",
            summary="No action.",
            rationale="agent invocation raised an exception",
        )
    finally:
        load_state_var.reset(load_token)
        current_event_var.reset(event_token)

    messages = result.get("messages", [])
    try:
        tool_calls = extract_tool_records(messages, load_id=load_id, event_id=event_id)
    except Exception as exc:
        logger.exception(
            "Tool-call extraction failed load_id=%s event_id=%s", load_id, event_id
        )
        return AgentDecision(
            noop=True,
            reason=f"tool-call extraction error: {type(exc).__name__}: {exc}",
            summary="No action.",
            rationale="failed to parse tool-call trajectory from agent messages",
            messages=messages,
        )

    summary, rationale = parse_final_answer(messages)
    if not summary and not rationale:
        logger.warning(
            "Agent final message missing SUMMARY/RATIONALE markers load_id=%s event_id=%s",
            load_id,
            event_id,
        )

    reason = ""
    if not tool_calls:
        reason = "agent produced no tool calls"
    elif not summary:
        reason = "agent final message missing SUMMARY/RATIONALE markers"

    return AgentDecision(
        state_delta=result.get("load_state") or {},
        active_timers=result.get("active_timers"),
        tool_calls=tool_calls,
        noop=not tool_calls,
        reason=reason,
        summary=summary,
        rationale=rationale,
        messages=messages,
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
                noop=True,
                reason="broker message ignored",
                summary="No action.",
                rationale="broker-originated inbound; ignored per SOP",
            )
        return await run_agent_for_event(load_state, active_timers or {}, event)
    return AgentDecision(
        noop=True,
        reason="no matching branch",
        summary="No action.",
        rationale="event type is not handled by an active SOP section",
    )
