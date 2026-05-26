"""Deterministic tracking-ping handler — no LLM involved."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from app.customers.base import get_customer_profile
from app.models.decision import ToolCallRecord
from app.worker.sops import task_for_milestone

_GEOFENCE_PING_KEY = "consecutive_geofence_pings"
_REQUIRED_PINGS = 3


def _now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _synthetic_record(
    tool: str,
    args: dict[str, Any],
    result: dict[str, Any],
    event_id: str,
    load_id: str,
) -> ToolCallRecord:
    return ToolCallRecord(
        tool_call_id=f"synthetic-{uuid.uuid4()}",
        event_id=event_id,
        load_id=load_id,
        tool=tool,
        arguments=args,
        result=result,
        created_at=_now_iso(),
    )


def handle_tracking_ping(
    load_state: dict[str, Any],
    event: dict[str, Any],
    session: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], list[ToolCallRecord]]:
    """Handle one tracking ping deterministically.

    Returns (load_state_delta, session_delta, tool_call_records).
    Caller merges state and appends records into the checkpoint.
    """
    customer_id = load_state.get("customer_id", "")
    load_id = load_state.get("load_id", "")
    event_id = event.get("event_id", "")
    tracking = event.get("tracking") or {}
    distance = tracking.get("distance_to_delivery_miles")

    profile = get_customer_profile(customer_id)
    geofence = profile.geofence_radius_miles

    in_geofence = isinstance(distance, (int, float)) and distance <= geofence
    consecutive = int(session.get(_GEOFENCE_PING_KEY, 0))
    consecutive = consecutive + 1 if in_geofence else 0

    session_delta = {_GEOFENCE_PING_KEY: consecutive}

    if consecutive < _REQUIRED_PINGS:
        return {}, session_delta, []

    # Three consecutive fresh pings inside the delivery geofence — arrived.
    new_milestone = "at_delivery"
    new_task = task_for_milestone(new_milestone)
    load_state_delta = {"milestone": new_milestone, "active_task": new_task}

    tool_records = [
        _synthetic_record(
            "update_load_state",
            {"target_state": new_milestone},
            {
                "ok": True,
                "previous_state": load_state.get("milestone", "on_route_to_delivery"),
                "new_state": new_milestone,
            },
            event_id,
            load_id,
        ),
        _synthetic_record(
            "cancel_timers",
            {},
            {"ok": True},
            event_id,
            load_id,
        ),
    ]
    return load_state_delta, session_delta, tool_records
