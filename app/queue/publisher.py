"""Publish work items to SQS FIFO."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import boto3

from app.config import get_settings
from app.queue.messages import WorkMessage

logger = logging.getLogger(__name__)


def _sqs_client():
    settings = get_settings()
    kwargs: dict = {"region_name": settings.aws_region}
    if settings.aws_endpoint_url:
        kwargs["endpoint_url"] = settings.aws_endpoint_url
    return boto3.client("sqs", **kwargs)


def publish_work_item(message: WorkMessage, *, delay_seconds: int = 0) -> None:
    settings = get_settings()
    client = _sqs_client()
    params: dict = {
        "QueueUrl": settings.sqs_queue_url,
        "MessageBody": message.to_json(),
        "MessageGroupId": message.load_id,
        "MessageDeduplicationId": message.dedup_id,
    }
    if delay_seconds > 0:
        params["DelaySeconds"] = min(delay_seconds, 900)
    client.send_message(**params)
    logger.info(
        "sqs_publish load_id=%s kind=%s dedup=%s delay=%s",
        message.load_id,
        message.kind,
        message.dedup_id,
        delay_seconds,
    )


def schedule_timer_message(
    *,
    load_id: str,
    timer_id: str,
    timer_type: str,
    fire_at_utc: str,
) -> None:
    """Enqueue a timer work item with SQS delay (max 900s; longer timers use capped delay)."""
    from app.queue.messages import dedup_id_for_timer

    now = datetime.now(timezone.utc)
    try:
        fire_at = datetime.fromisoformat(fire_at_utc.replace("Z", "+00:00"))
        if fire_at.tzinfo is None:
            fire_at = fire_at.replace(tzinfo=timezone.utc)
        delay = max(0, int((fire_at - now).total_seconds()))
    except ValueError:
        delay = 0

    if delay > 900:
        logger.warning(
            "timer delay %ss exceeds SQS max; capping at 900s timer_id=%s",
            delay,
            timer_id,
        )
        delay = 900

    msg = WorkMessage(
        load_id=load_id,
        kind="timer",
        payload={
            "event_id": f"timer-{timer_id}",
            "timer_id": timer_id,
            "timer_type": timer_type,
        },
        dedup_id=dedup_id_for_timer(timer_id),
    )
    publish_work_item(msg, delay_seconds=delay)
