"""Mocked challenge tools as LangChain @tool primitives."""

from __future__ import annotations

import uuid
from typing import Any

from langchain_core.tools import BaseTool, tool

from app.worker.load_data import get_load_field
from app.tools.context import current_event_var, load_state_var


def _ok(**kwargs: Any) -> dict[str, Any]:
    return {"ok": True, **kwargs}


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


@tool
def send_slack_message(audience: str, message: str, escalation_type: str = "") -> dict[str, Any]:
    """Send an internal or broker-visible Slack notification."""
    return _ok(channel="slack", message_id=f"slack-{uuid.uuid4()}")


def _extract_attachments(event: dict[str, Any]) -> list[dict[str, Any]]:
    if event.get("event_type") == "inbound_communication":
        return event.get("inbound_communication", {}).get("attachments", [])
    return []


@tool
def check_attachment(attachment_id: str) -> dict[str, Any]:
    """Classify an attachment from the current inbound communication."""
    categories = ["other"]
    description = "Unknown attachment"
    event = current_event_var.get()
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


@tool
def update_load_state(target_state: str) -> dict[str, Any]:
    """Update the load milestone/state."""
    load_state = load_state_var.get()
    previous = load_state.get("milestone", "on_route_to_delivery")
    return {"ok": True, "previous_state": previous, "new_state": target_state}


@tool
def update_eta(target_location: str, eta_utc: str) -> dict[str, Any]:
    """Update the ETA for a target location."""
    return _ok(target_location=target_location, eta_utc=eta_utc)


@tool
def create_timer(timer_type: str, fire_at_utc: str, timer_id: str = "") -> dict[str, Any]:
    """Schedule a follow-up timer."""
    return _ok(timer_id=timer_id or f"timer-{uuid.uuid4()}")


@tool
def cancel_timer(timer_id: str) -> dict[str, Any]:
    """Cancel a single timer by id."""
    return _ok()


@tool
def cancel_timers(timer_type: str | None = None) -> dict[str, Any]:
    """Cancel timers, optionally filtered by timer_type."""
    return _ok()


@tool
def create_task(title: str, description: str, task_type: str) -> dict[str, Any]:
    """Create an operational task for the team."""
    return _ok(task_id=f"task-{uuid.uuid4()}")


@tool
def create_issue(title: str, description: str, issue_type: str) -> dict[str, Any]:
    """Create an operational issue record."""
    return _ok(issue_id=f"issue-{uuid.uuid4()}")


@tool
def get_load_info(field: str) -> dict[str, Any]:
    """Read a field from the current load data."""
    load_state = load_state_var.get()
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
def get_appointment_time(stop_type: str) -> dict[str, Any]:
    """Get appointment details for a pickup or delivery stop."""
    load_state = load_state_var.get()
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
