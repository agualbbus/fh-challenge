"""HTTP routes."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, status

from app.api.schemas import (
    AcceptedResponse,
    InboundCommunicationEvent,
    LoadSeedRequest,
    LoadUpdateEvent,
    SubmitTaskRequest,
    TrackingEvent,
)
from app.config import get_settings
from app.worker.graph import thread_id_for_load
from app.queue.messages import (
    WorkMessage,
    dedup_id_for_event,
    dedup_id_for_seed,
    dedup_id_for_task,
)
from app.queue.publisher import publish_work_item

logger = logging.getLogger(__name__)
router = APIRouter()


def _workflow_id(load_id: str) -> str:
    return thread_id_for_load(load_id)


def _seed_from_load(body: LoadSeedRequest) -> dict:
    return {
        "customer_id": body.customer_id,
        "load_data": body.load_data.model_dump(mode="json"),
        "milestone": body.initial_state or "on_route_to_delivery",
    }


@router.get("/health")
async def health() -> dict:
    """Liveness probe; reports Postgres and SQS reachability when configured."""
    body: dict = {"status": "ok"}
    settings = get_settings()

    try:
        import boto3

        kwargs: dict = {"region_name": settings.aws_region}
        if settings.aws_endpoint_url:
            kwargs["endpoint_url"] = settings.aws_endpoint_url
        sqs = boto3.client("sqs", **kwargs)
        sqs.get_queue_attributes(
            QueueUrl=settings.sqs_queue_url,
            AttributeNames=["QueueArn"],
        )
        body["sqs"] = "ok"
    except Exception as exc:  # noqa: BLE001
        body["sqs"] = "unreachable"
        body["sqs_error"] = str(exc)

    try:
        import psycopg

        with psycopg.connect(settings.database_url, connect_timeout=3) as conn:
            conn.execute("SELECT 1")
        body["postgres"] = "ok"
    except Exception as exc:  # noqa: BLE001
        body["postgres"] = "unreachable"
        body["postgres_error"] = str(exc)

    return body


@router.post("/loads", status_code=status.HTTP_202_ACCEPTED, response_model=AcceptedResponse)
async def create_load(body: LoadSeedRequest) -> AcceptedResponse:
    seed = _seed_from_load(body)
    msg = WorkMessage(
        load_id=body.load_id,
        kind="seed",
        payload=seed,
        dedup_id=dedup_id_for_seed(body.load_id),
    )
    try:
        publish_work_item(msg)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return AcceptedResponse(load_id=body.load_id, workflow_id=_workflow_id(body.load_id))


@router.post(
    "/submit-task",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=AcceptedResponse,
)
async def submit_task(body: SubmitTaskRequest) -> AcceptedResponse:
    payload = body.model_dump(mode="json")
    msg = WorkMessage(
        load_id=body.load_id,
        kind="task",
        payload=payload,
        dedup_id=dedup_id_for_task(payload),
    )
    try:
        publish_work_item(msg)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return AcceptedResponse(load_id=body.load_id, workflow_id=_workflow_id(body.load_id))


@router.post(
    "/events/inbound-communication",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=AcceptedResponse,
)
async def inbound_communication(body: InboundCommunicationEvent) -> AcceptedResponse:
    payload = body.model_dump(mode="json")
    msg = WorkMessage(
        load_id=body.load_id,
        kind="event",
        payload=payload,
        dedup_id=dedup_id_for_event(payload),
    )
    try:
        publish_work_item(msg)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return AcceptedResponse(load_id=body.load_id, workflow_id=_workflow_id(body.load_id))


@router.post(
    "/events/tracking",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=AcceptedResponse,
)
async def tracking_event(body: TrackingEvent) -> AcceptedResponse:
    payload = body.model_dump(mode="json")
    msg = WorkMessage(
        load_id=body.load_id,
        kind="event",
        payload=payload,
        dedup_id=dedup_id_for_event(payload),
    )
    try:
        publish_work_item(msg)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return AcceptedResponse(load_id=body.load_id, workflow_id=_workflow_id(body.load_id))


@router.post(
    "/events/load-update",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=AcceptedResponse,
)
async def load_update(body: LoadUpdateEvent) -> AcceptedResponse:
    payload = body.model_dump(mode="json")
    msg = WorkMessage(
        load_id=body.load_id,
        kind="event",
        payload=payload,
        dedup_id=dedup_id_for_event(payload),
    )
    try:
        publish_work_item(msg)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return AcceptedResponse(load_id=body.load_id, workflow_id=_workflow_id(body.load_id))
