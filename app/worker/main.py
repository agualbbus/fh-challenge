"""Worker bootstrap — SQS consumer + LangGraph with Postgres checkpoints."""

from __future__ import annotations

import logging

from app.config import get_settings
from app.customers.base import get_customer_profiles
from app.queue.consumer import run_consumer
from app.queue.messages import WorkMessage
from app.worker.checkpointer import close_checkpointer, init_checkpointer
from app.worker.graph import process_work_message

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main() -> None:
    settings = get_settings()
    get_customer_profiles()

    checkpointer = await init_checkpointer(settings.database_url)

    logger.info(
        "Worker ready queue=%s db=%s model_mode=%s",
        settings.sqs_queue_url,
        settings.database_url.split("@")[-1],
        settings.model_mode,
    )

    try:
        async def on_message(msg: WorkMessage) -> None:
            await process_work_message(checkpointer, msg)

        await run_consumer(on_message)
    finally:
        await close_checkpointer()
