"""Temporal worker — polls task queue and runs workflows/activities."""

from __future__ import annotations

import asyncio
import logging

from temporalio.client import Client
from temporalio.worker import Worker

from app.config import get_settings
from app.workflows.load_workflow import LoadWorkflow

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main() -> None:
    settings = get_settings()
    connect_kwargs: dict = {"namespace": settings.temporal_namespace}
    if settings.temporal_api_key:
        connect_kwargs["api_key"] = settings.temporal_api_key

    logger.info(
        "Connecting to Temporal at %s namespace=%s queue=%s",
        settings.temporal_address,
        settings.temporal_namespace,
        settings.temporal_task_queue,
    )
    client = await Client.connect(settings.temporal_address, **connect_kwargs)

    worker = Worker(
        client,
        task_queue=settings.temporal_task_queue,
        workflows=[LoadWorkflow],
    )
    logger.info("Worker started on task queue %s", settings.temporal_task_queue)
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
