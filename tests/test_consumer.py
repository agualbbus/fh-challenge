"""SQS consumer — receive_message is monkeypatched to feed canned batches."""

from __future__ import annotations

import pytest

from app.queue import consumer
from app.queue.messages import WorkMessage


class _StopConsumer(Exception):
    pass


class FakeSqs:
    def __init__(self, batches: list[list[dict]]) -> None:
        self._batches = list(batches)
        self.deleted: list[str] = []

    def receive_message(self, **_kwargs) -> dict:
        if not self._batches:
            raise _StopConsumer
        return {"Messages": self._batches.pop(0)}

    def delete_message(self, *, QueueUrl: str, ReceiptHandle: str) -> None:  # noqa: N803
        del QueueUrl
        self.deleted.append(ReceiptHandle)


@pytest.fixture(autouse=True)
def _patch_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    class S:
        aws_region = "us-east-1"
        aws_endpoint_url = None
        sqs_queue_url = "http://q"

    monkeypatch.setattr("app.config.get_settings", lambda: S())


async def _run_until_stop(handler):
    try:
        await consumer.run_consumer(handler)
    except _StopConsumer:
        pass


def _make_msg(load_id="L1", kind="event", dedup="d-1") -> dict:
    body = WorkMessage(load_id=load_id, kind=kind, payload={"x": 1}, dedup_id=dedup).to_json()
    return {"Body": body, "ReceiptHandle": f"rcpt-{dedup}", "MessageId": f"mid-{dedup}"}


@pytest.mark.asyncio
async def test_consumer_deletes_after_successful_handler(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeSqs([[_make_msg(dedup="ok-1")], []])
    monkeypatch.setattr(consumer, "_sqs_client", lambda _s: fake)

    handled: list[WorkMessage] = []

    async def handler(msg: WorkMessage) -> None:
        handled.append(msg)

    await _run_until_stop(handler)
    assert handled[0].dedup_id == "ok-1"
    assert fake.deleted == ["rcpt-ok-1"]


@pytest.mark.asyncio
async def test_consumer_drops_poison_message(monkeypatch: pytest.MonkeyPatch) -> None:
    poison = {"Body": "not json", "ReceiptHandle": "rcpt-poison", "MessageId": "mp"}
    fake = FakeSqs([[poison]])
    monkeypatch.setattr(consumer, "_sqs_client", lambda _s: fake)

    handled = []

    async def handler(msg: WorkMessage) -> None:
        handled.append(msg)

    await _run_until_stop(handler)
    assert handled == []
    assert fake.deleted == ["rcpt-poison"]


@pytest.mark.asyncio
async def test_consumer_leaves_message_on_handler_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeSqs([[_make_msg(dedup="fail-1")], []])
    monkeypatch.setattr(consumer, "_sqs_client", lambda _s: fake)

    async def handler(_msg: WorkMessage) -> None:
        raise RuntimeError("boom")

    await _run_until_stop(handler)
    assert fake.deleted == []  # not acked
