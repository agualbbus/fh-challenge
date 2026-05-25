"""Mocked challenge tools as LangChain @tool primitives."""

from __future__ import annotations

import json
import uuid
from typing import Any, Literal

from langchain.tools import ToolRuntime, tool
from langchain_core.messages import ToolMessage
from langchain_core.tools import BaseTool
from langgraph.types import Command

from app.queue.publisher import schedule_timer_message
from app.tools.context import current_event_var, load_state_var
from app.worker.load_data import get_load_field


def _ok(**kwargs: Any) -> dict[str, Any]:
    return {"ok": True, **kwargs}


def _runtime_load_state(runtime: ToolRuntime) -> dict[str, Any]:
    return dict(runtime.state.get("load_state") or load_state_var.get() or {})


def _runtime_active_timers(runtime: ToolRuntime) -> dict[str, dict[str, Any]]:
    return dict(runtime.state.get("active_timers") or {})


def _tool_message(result: dict[str, Any], runtime: ToolRuntime) -> ToolMessage:
    return ToolMessage(
        content=json.dumps(result),
        tool_call_id=runtime.tool_call_id or "",
    )


def _state_command(result: dict[str, Any], runtime: ToolRuntime, **updates: Any) -> Command:
    return Command(
        update={
            **updates,
            "messages": [_tool_message(result, runtime)],
        }
    )


@tool
def send_sms(recipient: str, message: str) -> dict[str, Any]:
    """Send an SMS to the driver or dispatcher."""
    return _ok(channel="sms", message_id=f"sms-{uuid.uuid4()}")


@tool
def send_email(recipient: str, subject: str, body: str) -> dict[str, Any]:
    """Send or reply to an operational email thread."""
    return _ok(channel="email", message_id=f"email-{uuid.uuid4()}")


@tool
def forward_email() -> dict[str, Any]:
    """Forward the current email and attachments to the broker special address."""
    return _ok(channel="email", message_id=f"forwarded-{uuid.uuid4()}")


SlackAudience = Literal["internal", "broker", "customer"]


@tool
def send_slack_message(
    audience: SlackAudience, message: str, escalation_type: str = ""
) -> dict[str, Any]:
    """Send an internal or broker-visible Slack notification."""
    return _ok(channel="slack", message_id=f"slack-{uuid.uuid4()}")


def _extract_attachments(event: dict[str, Any]) -> list[dict[str, Any]]:
    if event.get("event_type") == "inbound_communication":
        return event.get("inbound_communication", {}).get("attachments", [])
    return []


@tool
def check_attachment(attachment_id: str, runtime: ToolRuntime) -> dict[str, Any]:
    """Classify an attachment from the current inbound communication."""
    categories = ["other"]
    description = "Unknown attachment"
    event = runtime.state.get("current_event") or current_event_var.get()
    for att in _extract_attachments(event):
        if att.get("attachment_id") == attachment_id:
            mock = att.get("mock_classification", {})
            categories = mock.get("categories", categories)
            description = mock.get("description", description)
            break
    return {
        "ok": True,
        "attachment_id": attachment_id,
        "categories": categories,
        "description": description,
    }


LoadMilestone = Literal[
    "on_route_to_delivery", "at_delivery", "delivered", "pod_collected"
]


@tool
def update_load_state(target_state: LoadMilestone, runtime: ToolRuntime) -> Command:
    """Update the load milestone/state."""
    load_state = _runtime_load_state(runtime)
    previous = load_state.get("milestone", "on_route_to_delivery")
    updated_load_state = {**load_state, "milestone": target_state}
    result = {"ok": True, "previous_state": previous, "new_state": target_state}
    return _state_command(result, runtime, load_state=updated_load_state)


EtaTarget = Literal["delivery"]
TimerType = Literal[
    "eta_followup", "pod_followup", "delivery_status_followup", "attachment_clarification"
]


@tool
def update_eta(target_location: EtaTarget, eta_utc: str) -> dict[str, Any]:
    """Store a driver-provided ETA for the target location."""
    return _ok(target_location=target_location, eta_utc=eta_utc)


@tool
def create_timer(
    timer_type: TimerType,
    fire_at_utc: str,
    runtime: ToolRuntime,
    timer_id: str = "",
) -> Command:
    """Schedule a follow-up timer."""
    load_state = _runtime_load_state(runtime)
    load_id = load_state.get("load_id", "")
    resolved_timer_id = timer_id or f"timer-{uuid.uuid4()}"
    active_timers = _runtime_active_timers(runtime)
    active_timers[resolved_timer_id] = {
        "timer_id": resolved_timer_id,
        "timer_type": timer_type,
        "fire_at_utc": fire_at_utc,
    }
    if load_id:
        schedule_timer_message(
            load_id=load_id,
            timer_id=resolved_timer_id,
            timer_type=timer_type,
            fire_at_utc=fire_at_utc,
        )
    result = _ok(timer_id=resolved_timer_id)
    return _state_command(result, runtime, active_timers=active_timers)


@tool
def cancel_timer(timer_id: str, runtime: ToolRuntime) -> Command:
    """Cancel a single timer by id."""
    active_timers = _runtime_active_timers(runtime)
    active_timers.pop(timer_id, None)
    return _state_command(_ok(), runtime, active_timers=active_timers)


@tool
def cancel_timers(runtime: ToolRuntime, timer_type: str | None = None) -> Command:
    """Cancel timers, optionally filtered by timer_type."""
    active_timers = _runtime_active_timers(runtime)
    if timer_type is None:
        active_timers = {}
    else:
        active_timers = {
            timer_id: timer
            for timer_id, timer in active_timers.items()
            if timer.get("timer_type") != timer_type
        }
    return _state_command(_ok(), runtime, active_timers=active_timers)


TaskType = Literal[
    "missing_load_info", "pod_review", "lumper_review", "manual_followup", "other"
]
IssueType = Literal["equipment_failure", "delivery_delay", "facility_problem", "other"]


@tool
def create_task(title: str, description: str, task_type: TaskType) -> dict[str, Any]:
    """Create a non-urgent human follow-up task."""
    return _ok(task_id=f"task-{uuid.uuid4()}")


@tool
def create_issue(title: str, description: str, issue_type: IssueType) -> dict[str, Any]:
    """Create an urgent operational issue."""
    return _ok(issue_id=f"issue-{uuid.uuid4()}")


@tool
def get_load_info(field: str, runtime: ToolRuntime) -> dict[str, Any]:
    """Read a field from the current load data."""
    load_state = _runtime_load_state(runtime)
    load_data = load_state.get("load_data", {})
    value = get_load_field(load_data, field)
    if value:
        return {"ok": True, "field": field, "value": value}
    return {"ok": False, "field": field, "error": "missing"}


@tool
def validate_eta(eta_utc: str, target_location: str = "delivery") -> dict[str, Any]:
    """Validate whether an ETA is plausible."""
    return _ok(eta_utc="2026-05-11T19:30:00Z", is_plausible=True)


@tool
def get_appointment_time(
    stop_type: Literal["pickup", "delivery"], runtime: ToolRuntime
) -> dict[str, Any]:
    """Get appointment details for a pickup or delivery stop."""
    load_state = _runtime_load_state(runtime)
    load_data = load_state.get("load_data", {})
    for stop in load_data.get("stops", []):
        if stop.get("type") == stop_type:
            return {
                "ok": True,
                "stop_type": stop_type,
                "appointment": stop.get("appointment", {}),
            }
    return {"ok": False, "stop_type": stop_type, "error": "missing"}


ALL_TOOLS: list[BaseTool] = [
    send_sms,
    send_email,
    forward_email,
    send_slack_message,
    check_attachment,
    update_load_state,
    update_eta,
    create_timer,
    cancel_timer,
    cancel_timers,
    create_task,
    create_issue,
    get_load_info,
    validate_eta,
    get_appointment_time,
]

TOOLS_BY_NAME: dict[str, BaseTool] = {t.name: t for t in ALL_TOOLS}
