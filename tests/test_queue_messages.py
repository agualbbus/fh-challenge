"""WorkMessage round-trip and dedup helpers."""

from __future__ import annotations

from app.queue.messages import (
    WorkMessage,
    dedup_id_for_event,
    dedup_id_for_seed,
    dedup_id_for_task,
    dedup_id_for_timer,
)


def test_work_message_roundtrip() -> None:
    msg = WorkMessage(
        load_id="load-1",
        kind="event",
        payload={"event_id": "e-1", "foo": "bar"},
        dedup_id="dedup-1",
    )
    parsed = WorkMessage.from_json(msg.to_json())
    assert parsed == msg


def test_from_json_generates_dedup_id_when_missing() -> None:
    raw = '{"load_id": "l", "kind": "seed", "payload": {}}'
    parsed = WorkMessage.from_json(raw)
    assert parsed.dedup_id  # uuid fallback


def test_dedup_helpers() -> None:
    assert dedup_id_for_seed("load-9") == "seed-load-9"
    assert dedup_id_for_timer("t-3") == "timer-t-3"
    assert dedup_id_for_event({"event_id": "evt-7"}) == "evt-7"
    assert dedup_id_for_task({"task_uuid": "task-7"}) == "task-7"


def test_dedup_event_fallback_is_uuid() -> None:
    dedup = dedup_id_for_event({})
    assert dedup and dedup != dedup_id_for_event({})
