"""Mocked tool primitives — invoked via .func with a fake ToolRuntime."""

from __future__ import annotations

import json
from typing import Any

import pytest

from app.tools import tools as tools_mod
from app.tools.tools import (
    _extract_attachments,
    cancel_timer,
    cancel_timers,
    check_attachment,
    create_issue,
    create_task,
    create_timer,
    forward_email,
    get_appointment_time,
    get_load_info,
    send_email,
    send_slack_message,
    send_sms,
    update_eta,
    update_load_state,
    validate_eta,
)


class FakeRuntime:
    def __init__(self, state: dict[str, Any] | None = None, tool_call_id: str = "tc-1") -> None:
        self.state = state or {}
        self.tool_call_id = tool_call_id


def test_simple_message_tools_return_ok_dict() -> None:
    assert send_sms.func(recipient="d", message="hi")["ok"] is True
    assert send_email.func(recipient="d", subject="s", body="b")["ok"] is True
    assert forward_email.func()["ok"] is True
    assert send_slack_message.func(audience="internal", message="hi")["ok"] is True
    assert update_eta.func(target_location="delivery", eta_utc="2026-05-11T19:30:00Z")["ok"] is True
    assert validate_eta.func(eta_utc="2026-05-11T19:30:00Z")["ok"] is True
    assert create_task.func(title="t", description="d", task_type="other")["ok"] is True
    assert create_issue.func(title="t", description="d", issue_type="other")["ok"] is True


def test_extract_attachments_only_for_inbound_comm() -> None:
    assert _extract_attachments({"event_type": "tracking"}) == []
    event = {
        "event_type": "inbound_communication",
        "inbound_communication": {"attachments": [{"attachment_id": "a1"}]},
    }
    assert _extract_attachments(event) == [{"attachment_id": "a1"}]


def test_check_attachment_returns_classification() -> None:
    event = {
        "event_type": "inbound_communication",
        "inbound_communication": {
            "attachments": [
                {
                    "attachment_id": "a1",
                    "mock_classification": {"categories": ["pod"], "description": "POD scan"},
                }
            ]
        },
    }
    runtime = FakeRuntime(state={"current_event": event})
    result = check_attachment.func(attachment_id="a1", runtime=runtime)
    assert result["categories"] == ["pod"]
    assert result["description"] == "POD scan"


def test_check_attachment_unknown_attachment_defaults() -> None:
    runtime = FakeRuntime(state={"current_event": {"event_type": "tracking"}})
    result = check_attachment.func(attachment_id="missing", runtime=runtime)
    assert result["categories"] == ["other"]


def test_update_load_state_returns_command_with_delta() -> None:
    runtime = FakeRuntime(state={"load_state": {"milestone": "on_route_to_delivery"}})
    cmd = update_load_state.func(target_state="delivered", runtime=runtime)
    updates = cmd.update
    assert updates["load_state"]["milestone"] == "delivered"
    assert len(updates["messages"]) == 1
    payload = json.loads(updates["messages"][0].content)
    assert payload["previous_state"] == "on_route_to_delivery"
    assert payload["new_state"] == "delivered"


def test_create_timer_publishes_and_stores(monkeypatch: pytest.MonkeyPatch) -> None:
    published: list[dict] = []

    def fake_publish(**kwargs):
        published.append(kwargs)

    monkeypatch.setattr(tools_mod, "schedule_timer_message", fake_publish)

    runtime = FakeRuntime(state={"load_state": {"load_id": "L1"}, "active_timers": {}})
    cmd = create_timer.func(
        timer_type="eta_followup",
        fire_at_utc="2026-05-11T19:30:00Z",
        runtime=runtime,
        timer_id="T1",
    )
    assert "T1" in cmd.update["active_timers"]
    assert published[0]["timer_id"] == "T1"


def test_create_timer_without_load_id_skips_publish(monkeypatch: pytest.MonkeyPatch) -> None:
    called: list[dict] = []
    monkeypatch.setattr(tools_mod, "schedule_timer_message", lambda **kw: called.append(kw))
    runtime = FakeRuntime(state={"load_state": {}, "active_timers": {}})
    create_timer.func(
        timer_type="eta_followup",
        fire_at_utc="2026-05-11T19:30:00Z",
        runtime=runtime,
        timer_id="T2",
    )
    assert called == []


def test_cancel_timer_removes_by_id() -> None:
    runtime = FakeRuntime(state={"active_timers": {"T1": {"timer_id": "T1"}}})
    cmd = cancel_timer.func(timer_id="T1", runtime=runtime)
    assert "T1" not in cmd.update["active_timers"]


def test_cancel_timers_clears_all_when_no_type() -> None:
    runtime = FakeRuntime(state={"active_timers": {"T1": {"timer_type": "x"}}})
    cmd = cancel_timers.func(runtime=runtime)
    assert cmd.update["active_timers"] == {}


def test_cancel_timers_filters_by_type() -> None:
    runtime = FakeRuntime(
        state={
            "active_timers": {
                "T1": {"timer_type": "eta_followup"},
                "T2": {"timer_type": "pod_followup"},
            }
        }
    )
    cmd = cancel_timers.func(runtime=runtime, timer_type="eta_followup")
    assert "T1" not in cmd.update["active_timers"]
    assert "T2" in cmd.update["active_timers"]


def test_get_load_info_hit_and_miss() -> None:
    load_data = {
        "stops": [
            {
                "type": "delivery",
                "address": {"line_1": "1 Main", "city": "X", "state": "Y", "postal_code": "Z"},
            }
        ]
    }
    runtime = FakeRuntime(state={"load_state": {"load_data": load_data}})
    hit = get_load_info.func(field="delivery_address", runtime=runtime)
    assert hit["ok"] is True
    miss = get_load_info.func(field="nope", runtime=runtime)
    assert miss["ok"] is False


def test_get_appointment_time_hit_and_miss() -> None:
    load_data = {
        "stops": [
            {"type": "delivery", "appointment": {"start_utc": "2026-05-11T18:00:00Z"}},
        ]
    }
    runtime = FakeRuntime(state={"load_state": {"load_data": load_data}})
    hit = get_appointment_time.func(stop_type="delivery", runtime=runtime)
    assert hit["ok"] is True
    miss = get_appointment_time.func(stop_type="pickup", runtime=runtime)
    assert miss["ok"] is False
