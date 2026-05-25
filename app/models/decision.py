"""Agent decision and tool-call record models."""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolCallRecord:
    tool_call_id: str
    event_id: str
    load_id: str
    tool: str
    arguments: dict[str, Any]
    result: dict[str, Any]
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


@dataclass
class AgentDecision:
    state_delta: dict[str, Any] = field(default_factory=dict)
    active_timers: dict[str, dict[str, Any]] | None = None
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    noop: bool = False
    reason: str = ""
    summary: str = ""
    rationale: str = ""
    messages: list[Any] = field(default_factory=list)
