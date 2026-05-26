"""SQS FIFO consumer — polls the queue and delegates each message to a handler.

Messages are dispatched concurrently as asyncio tasks. SQS FIFO guarantees only
one in-flight message per ``MessageGroupId`` (= ``load_id``) at a time, so
per-load ordering is preserved automatically. A semaphore bounds total
concurrency to keep DB/LLM pressure reasonable.
"""

from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import Awaitable, Callable

import boto3

from app.queue.messages import WorkMessage

logger = logging.getLogger(__name__)

MessageHandler = Callable[[WorkMessage], Awaitable[None]]

# Bound concurrent in-flight handlers. Set high enough that parallel eval runs
# don't queue behind each other; low enough to avoid LLM rate-limit storms.
_DEFAULT_CONCURRENCY = int(os.getenv("WORKER_CONCURRENCY", "10"))
# Max SQS receive per poll (SQS hard cap is 10).
_MAX_RECEIVE = 10


def _sqs_client(settings):
    kwargs: dict = {"region_name": settings.aws_region}
    if settings.aws_endpoint_url:
        kwargs["endpoint_url"] = settings.aws_endpoint_url
    return boto3.client("sqs", **kwargs)


async def _handle_one(
    client,
    queue_url: str,
    raw: dict,
    handler: MessageHandler,
    semaphore: asyncio.Semaphore,
) -> None:
    receipt = raw["ReceiptHandle"]
    message_id = raw.get("MessageId", "?")
    try:
        work = WorkMessage.from_json(raw["Body"])
    except (ValueError, KeyError, TypeError) as exc:
        logger.error(
            "Dropping poison SQS message id=%s err=%s body=%r",
            message_id,
            exc,
            raw.get("Body", "")[:500],
        )
        await asyncio.to_thread(client.delete_message, QueueUrl=queue_url, ReceiptHandle=receipt)
        return

    async with semaphore:
        try:
            await handler(work)
        except Exception:
            logger.exception(
                "Handler failed; message will be retried load_id=%s kind=%s message_id=%s",
                work.load_id,
                work.kind,
                message_id,
            )
            return

        await asyncio.to_thread(client.delete_message, QueueUrl=queue_url, ReceiptHandle=receipt)


async def run_consumer(handler: MessageHandler) -> None:
    from app.config import get_settings

    settings = get_settings()
    client = _sqs_client(settings)
    semaphore = asyncio.Semaphore(_DEFAULT_CONCURRENCY)
    in_flight: set[asyncio.Task] = set()
    logger.info(
        "SQS consumer started queue=%s concurrency=%d",
        settings.sqs_queue_url,
        _DEFAULT_CONCURRENCY,
    )

    while True:
        response = await asyncio.to_thread(
            client.receive_message,
            QueueUrl=settings.sqs_queue_url,
            MaxNumberOfMessages=_MAX_RECEIVE,
            WaitTimeSeconds=20,
            AttributeNames=["All"],
        )
        messages = response.get("Messages", [])
        for raw in messages:
            task = asyncio.create_task(
                _handle_one(client, settings.sqs_queue_url, raw, handler, semaphore)
            )
            in_flight.add(task)
            task.add_done_callback(in_flight.discard)
