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
            try:
                work = WorkMessage.from_json(raw["Body"])
                await handler(work)
                await asyncio.to_thread(
                    client.delete_message,
                    QueueUrl=settings.sqs_queue_url,
                    ReceiptHandle=receipt,
                )
            except Exception:
                logger.exception("Failed to process SQS message")
                # Leave message for retry / DLQ
