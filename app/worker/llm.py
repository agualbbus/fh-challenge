"""LLM factory: OpenRouter chat model for create_agent."""

from __future__ import annotations

from langchain_openrouter import ChatOpenRouter

from app.config import get_settings


def get_chat_model():
    """Return the OpenRouter chat model used by create_agent."""
    settings = get_settings()
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
