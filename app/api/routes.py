"""HTTP routes."""

from __future__ import annotations

from fastapi import APIRouter

from app.config import get_settings

router = APIRouter()


@router.get("/health")
async def health() -> dict:
    """Liveness probe; optionally reports Temporal reachability."""
    body: dict = {"status": "ok"}
    settings = get_settings()
    if not settings.temporal_address:
        return body

    try:
        from temporalio.client import Client

        connect_kwargs: dict = {
            "namespace": settings.temporal_namespace,
        }
        if settings.temporal_api_key:
            connect_kwargs["api_key"] = settings.temporal_api_key

        client = await Client.connect(settings.temporal_address, **connect_kwargs)
        await client.service_client.check_health()
        body["temporal"] = "ok"
    except Exception as exc:  # noqa: BLE001 — health must not fail hard on Temporal
        body["temporal"] = "unreachable"
        body["temporal_error"] = str(exc)

    return body
