"""SQS FIFO consumer — polls the queue and delegates each message to a handler."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

import boto3

from app.queue.messages import WorkMessage

logger = logging.getLogger(__name__)

MessageHandler = Callable[[WorkMessage], Awaitable[None]]


def _sqs_client(settings):
    kwargs: dict = {"region_name": settings.aws_region}
    if settings.aws_endpoint_url:
        kwargs["endpoint_url"] = settings.aws_endpoint_url
    return boto3.client("sqs", **kwargs)


async def run_consumer(handler: MessageHandler) -> None:
    from app.config import get_settings

    settings = get_settings()
    client = _sqs_client(settings)
    logger.info("SQS consumer started queue=%s", settings.sqs_queue_url)

    while True:
        response = await asyncio.to_thread(
            client.receive_message,
            QueueUrl=settings.sqs_queue_url,
            MaxNumberOfMessages=1,
            WaitTimeSeconds=20,
            AttributeNames=["All"],
        )
        messages = response.get("Messages", [])
        if not messages:
            continue

        for raw in messages:
            receipt = raw["ReceiptHandle"]
            message_id = raw.get("MessageId", "?")
            try:
                work = WorkMessage.from_json(raw["Body"])
            except (ValueError, KeyError, TypeError) as exc:
                # Poison message — invalid JSON or missing required fields.
                # Retrying won't help, so drop it to keep the worker moving.
                logger.error(
                    "Dropping poison SQS message id=%s err=%s body=%r",
                    message_id,
                    exc,
                    raw.get("Body", "")[:500],
                )
                await asyncio.to_thread(
                    client.delete_message,
                    QueueUrl=settings.sqs_queue_url,
                    ReceiptHandle=receipt,
                )
                continue

            try:
                await handler(work)
            except Exception:
                # Transient handler failure: leave the message so SQS redelivers
                # (and eventually moves it to the DLQ via max-receive-count).
                logger.exception(
                    "Handler failed; message will be retried load_id=%s kind=%s message_id=%s",
                    work.load_id,
                    work.kind,
                    message_id,
                )
                continue

            await asyncio.to_thread(
                client.delete_message,
                QueueUrl=settings.sqs_queue_url,
                ReceiptHandle=receipt,
            )
