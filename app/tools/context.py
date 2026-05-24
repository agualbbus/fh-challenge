"""Per-invocation context for stateful mocked tools (hidden from tool schemas)."""

from __future__ import annotations

from contextvars import ContextVar
from typing import Any

load_state_var: ContextVar[dict[str, Any]] = ContextVar("load_state", default={})
current_event_var: ContextVar[dict[str, Any]] = ContextVar("current_event", default={})
