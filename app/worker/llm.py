"""LLM factory: OpenRouter (live) or fixture mock (MODEL_MODE=mock)."""

from __future__ import annotations

from app.config import get_settings
from app.tools.context import current_event_var, load_state_var


def get_chat_model():
    """Return chat model for create_agent (OpenRouter or per-event mock)."""
    settings = get_settings()
    if settings.model_mode == "mock":
        from app.worker.mock_model import build_mock_model

        load_state = load_state_var.get() or {}
        event = current_event_var.get() or {}
        return build_mock_model(load_state, event)

    from langchain_openrouter import ChatOpenRouter

    if not settings.openrouter_api_key:
        raise RuntimeError("OPENROUTER_API_KEY is required")
    return ChatOpenRouter(
        model=settings.openrouter_model_primary,
        temperature=0.2,
        api_key=settings.openrouter_api_key,
        base_url=settings.openrouter_base_url,
        app_url=settings.openrouter_http_referer,
        app_title=settings.openrouter_app_title,
    )
