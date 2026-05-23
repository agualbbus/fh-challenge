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
    temporal_address: str
    temporal_namespace: str
    temporal_api_key: str | None
    temporal_task_queue: str
    model_mode: str
    langfuse_enabled: bool
    langfuse_public_key: str
    langfuse_secret_key: str
    langfuse_base_url: str


def get_settings() -> Settings:
    api_key = _env("TEMPORAL_API_KEY")
    return Settings(
        temporal_address=_env("TEMPORAL_ADDRESS", "localhost:7233"),
        temporal_namespace=_env("TEMPORAL_NAMESPACE", "default"),
        temporal_api_key=api_key if api_key else None,
        temporal_task_queue=_env("TEMPORAL_TASK_QUEUE", "freight-watchtower"),
        model_mode=_env("MODEL_MODE", "mock"),
        langfuse_enabled=_env("LANGFUSE_ENABLED", "false").lower() == "true",
        langfuse_public_key=_env("LANGFUSE_PUBLIC_KEY", ""),
        langfuse_secret_key=_env("LANGFUSE_SECRET_KEY", ""),
        langfuse_base_url=_env("LANGFUSE_BASE_URL", "https://cloud.langfuse.com"),
    )
