"""SQS publisher — boto3 client is monkeypatched."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.queue import publisher
from app.queue.messages import WorkMessage


class FakeSqs:
    def __init__(self) -> None:
        self.sent: list[dict] = []

    def send_message(self, **kwargs) -> dict:
        self.sent.append(kwargs)
        return {"MessageId": "mid-1"}


@pytest.fixture
def fake_sqs(monkeypatch: pytest.MonkeyPatch) -> FakeSqs:
    fake = FakeSqs()
    monkeypatch.setattr(publisher, "_sqs_client", lambda: fake)
    return fake


def test_publish_work_item_no_delay(fake_sqs: FakeSqs) -> None:
    msg = WorkMessage(load_id="L1", kind="event", payload={"a": 1}, dedup_id="d-1")
    publisher.publish_work_item(msg)
    assert len(fake_sqs.sent) == 1
    params = fake_sqs.sent[0]
    assert params["MessageGroupId"] == "L1"
    assert params["MessageDeduplicationId"] == "d-1"
    assert "DelaySeconds" not in params


def test_publish_work_item_with_delay_caps_at_900(fake_sqs: FakeSqs) -> None:
    msg = WorkMessage(load_id="L1", kind="timer", payload={}, dedup_id="d-2")
    publisher.publish_work_item(msg, delay_seconds=5000)
    assert fake_sqs.sent[0]["DelaySeconds"] == 900


def test_delay_seconds_handles_bad_iso() -> None:
    assert publisher._delay_seconds("not-a-date") == 0


def test_delay_seconds_caps_at_900() -> None:
    future = (datetime.now(timezone.utc) + timedelta(hours=5)).isoformat()
    assert publisher._delay_seconds(future) == 900


def test_delay_seconds_floor_at_zero() -> None:
    past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    assert publisher._delay_seconds(past) == 0


def test_schedule_timer_message_calls_publish(fake_sqs: FakeSqs) -> None:
    future = (datetime.now(timezone.utc) + timedelta(hours=5)).isoformat()
    publisher.schedule_timer_message(
        load_id="L1",
        timer_id="T1",
        timer_type="eta_followup",
        fire_at_utc=future,
    )
    params = fake_sqs.sent[0]
    assert params["DelaySeconds"] == 900
    assert params["MessageDeduplicationId"] == "timer-T1"


def test_sqs_client_passes_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict = {}

    def fake_boto(_name, **kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(publisher.boto3, "client", fake_boto)
    monkeypatch.setenv("AWS_ENDPOINT_URL", "http://localhost:9324")
    publisher._sqs_client()
    assert captured["endpoint_url"] == "http://localhost:9324"
