"""LangGraph state schema for per-load processing."""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict


class LoadGraphState(TypedDict, total=False):
    """Persistent per-load state checkpointed in PostgreSQL."""

    load_id: str
    kind: str
    payload: dict[str, Any]
    load_state: dict[str, Any]
    session: dict[str, Any]
    tool_calls: Annotated[list[dict[str, Any]], operator.add]
    active_timers: dict[str, dict[str, Any]]
    messages: list[Any]
