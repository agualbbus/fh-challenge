"""Agent decision and workflow work-item models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


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
        return {
            "tool_call_id": self.tool_call_id,
            "event_id": self.event_id,
            "load_id": self.load_id,
            "tool": self.tool,
            "arguments": self.arguments,
            "result": self.result,
            "created_at": self.created_at,
        }


@dataclass
class AgentDecision:
    state_delta: dict[str, Any] = field(default_factory=dict)
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    timer_ops: list[dict[str, Any]] = field(default_factory=list)
    noop: bool = False
    reason: str = ""
    sop_branch: str = ""


WorkItemKind = Literal["event", "task", "timer"]


@dataclass
class WorkItem:
    kind: WorkItemKind
    payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "payload": self.payload}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WorkItem:
        return cls(kind=data["kind"], payload=data["payload"])
