"""HTTP route validation — write endpoints with a fake SQS publisher."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api import routes
from app.api.main import app
from app.queue.messages import WorkMessage


@pytest.fixture
def published() -> list[WorkMessage]:
    return []


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch, published: list[WorkMessage]) -> TestClient:
    def fake_publish(message: WorkMessage) -> None:
        published.append(message)

    monkeypatch.setattr(routes, "publish_work_item", fake_publish)
    return TestClient(app)


def _load_seed_payload(base_load_data: dict, *, customer_id: str = "customer_a") -> dict:
    return {
        "load_id": "load-api-1",
        "customer_id": customer_id,
        "load_data": base_load_data,
    }


def test_create_load_accepts_valid_body(
    client: TestClient, base_load_data: dict, published: list[WorkMessage]
) -> None:
    body = _load_seed_payload(base_load_data)
    resp = client.post("/loads", json=body)
    assert resp.status_code == 202
    data = resp.json()
    assert data["accepted"] is True
    assert data["load_id"] == "load-api-1"
    assert data["workflow_id"] == "load-load-api-1"
    assert len(published) == 1
    msg = published[0]
    assert msg.load_id == "load-api-1"
    assert msg.kind == "seed"
    assert msg.dedup_id == "seed-load-api-1"


def test_create_load_rejects_unknown_customer(client: TestClient, base_load_data: dict) -> None:
    body = _load_seed_payload(base_load_data, customer_id="nope")
    resp = client.post("/loads", json=body)
    assert resp.status_code == 422


def test_create_load_rejects_missing_field(client: TestClient) -> None:
    resp = client.post("/loads", json={"load_id": "x", "customer_id": "customer_a"})
    assert resp.status_code == 422


def test_inbound_communication_publishes_event(
    client: TestClient, published: list[WorkMessage]
) -> None:
    body = {
        "event_id": "evt-1",
        "load_id": "load-api-1",
        "customer_id": "customer_a",
        "occurred_at": "2026-05-11T17:05:00Z",
        "inbound_communication": {
            "channel": "sms",
            "sender_type": "driver",
            "content": "ETA?",
            "attachments": [],
        },
    }
    resp = client.post("/events/inbound-communication", json=body)
    assert resp.status_code == 202
    assert published[0].kind == "event"
    assert published[0].dedup_id == "evt-1"


def test_tracking_event_accepted(client: TestClient, published: list[WorkMessage]) -> None:
    body = {
        "event_id": "trk-1",
        "load_id": "load-api-1",
        "customer_id": "customer_a",
        "occurred_at": "2026-05-11T17:05:00Z",
        "tracking": {
            "tracking_id": "t-1",
            "lat": 32.0,
            "lng": -96.0,
            "distance_to_delivery_miles": 5.2,
            "ping_sequence": 1,
        },
    }
    resp = client.post("/events/tracking", json=body)
    assert resp.status_code == 202
    assert published[0].kind == "event"


def test_load_update_accepted(client: TestClient, published: list[WorkMessage]) -> None:
    body = {
        "event_id": "lu-1",
        "load_id": "load-api-1",
        "customer_id": "customer_a",
        "occurred_at": "2026-05-11T17:05:00Z",
        "load_update": {"milestone_state": "at_delivery"},
    }
    resp = client.post("/events/load-update", json=body)
    assert resp.status_code == 202
    assert published[0].kind == "event"


def test_submit_task_accepted(client: TestClient, published: list[WorkMessage]) -> None:
    body = {
        "task_uuid": "task-1",
        "load_id": "load-api-1",
        "customer_id": "customer_a",
        "task_instruction_type": "delivery_eta_checkpoint",
        "requested_at": "2026-05-11T17:05:00Z",
    }
    resp = client.post("/submit-task", json=body)
    assert resp.status_code == 202
    assert published[0].kind == "task"
    assert published[0].dedup_id == "task-1"


def test_publisher_failure_returns_502(
    monkeypatch: pytest.MonkeyPatch, base_load_data: dict
) -> None:
    def boom(_message: WorkMessage) -> None:
        raise RuntimeError("sqs down")

    monkeypatch.setattr(routes, "publish_work_item", boom)
    client = TestClient(app)
    resp = client.post("/loads", json=_load_seed_payload(base_load_data))
    assert resp.status_code == 502
