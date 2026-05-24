"""Application settings loaded from environment (and optional .env via python-dotenv)."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _env(key: str, default: str = "") -> str:
    return os.getenv(key, default)


@dataclass(frozen=True)
class Settings:
    database_url: str
    sqs_queue_url: str
    aws_region: str
    aws_endpoint_url: str | None
    model_mode: str
    openrouter_api_key: str | None
    openrouter_model_primary: str
    openrouter_model_fallback: str
    openrouter_base_url: str
    openrouter_http_referer: str
    openrouter_app_title: str
    langchain_tracing_v2: bool
    langchain_api_key: str | None
    langchain_project: str
    api_base_url: str


def get_settings() -> Settings:
    or_key = _env("OPENROUTER_API_KEY")
    lc_key = _env("LANGCHAIN_API_KEY")
    endpoint = _env("AWS_ENDPOINT_URL")
    return Settings(
        database_url=_env(
            "DATABASE_URL",
            "postgresql://watchtower:watchtower@localhost:5432/watchtower",
        ),
        sqs_queue_url=_env(
            "SQS_QUEUE_URL",
            "http://localhost:9324/000000000000/freight-watchtower.fifo",
        ),
        aws_region=_env("AWS_REGION", "us-east-1"),
        aws_endpoint_url=endpoint if endpoint else None,
        model_mode=_env("MODEL_MODE", "mock"),
        openrouter_api_key=or_key if or_key else None,
        openrouter_model_primary=_env(
            "OPENROUTER_MODEL_PRIMARY", "anthropic/claude-sonnet-latest"
        ),
        openrouter_model_fallback=_env("OPENROUTER_MODEL_FALLBACK", "z-ai/glm-5.1"),
        openrouter_base_url=_env("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
        openrouter_http_referer=_env(
            "OPENROUTER_HTTP_REFERER", "https://github.com/freight-hero/watchtower"
        ),
        openrouter_app_title=_env("OPENROUTER_APP_TITLE", "FreightHero Watchtower"),
        langchain_tracing_v2=_env("LANGCHAIN_TRACING_V2", "false").lower() == "true",
        langchain_api_key=lc_key if lc_key else None,
        langchain_project=_env("LANGCHAIN_PROJECT", "freight-watchtower"),
        api_base_url=_env("API_BASE_URL", "http://localhost:8000"),
    )
