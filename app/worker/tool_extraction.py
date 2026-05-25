"""Extract `ToolCallRecord`s from a LangChain message trace."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from langchain_core.messages import AIMessage, ToolMessage

from app.models.decision import ToolCallRecord


def _now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _coerce_result(content: Any) -> dict[str, Any]:
    if isinstance(content, str):
        try:
            content = json.loads(content)
        except json.JSONDecodeError:
            return {"result": content}
    if isinstance(content, dict):
        return content
    return {"result": content}


def extract_tool_records(
    messages: list[Any],
    *,
    load_id: str,
    event_id: str,
) -> list[ToolCallRecord]:
    """Pair AIMessage tool_calls with their ToolMessage results, in order."""
    records: list[ToolCallRecord] = []
    pending: dict[str, dict[str, Any]] = {}

    for msg in messages:
        if isinstance(msg, AIMessage) and msg.tool_calls:
            for tc in msg.tool_calls:
                tc_id = tc.get("id", str(uuid.uuid4()))
                pending[tc_id] = {
                    "name": tc.get("name", ""),
                    "args": tc.get("args", {}),
                }
        elif isinstance(msg, ToolMessage):
            info = pending.pop(msg.tool_call_id, {})
            records.append(
                ToolCallRecord(
                    tool_call_id=msg.tool_call_id,
                    event_id=event_id,
                    load_id=load_id,
                    tool=info.get("name", ""),
                    arguments=info.get("args", {}),
                    result=_coerce_result(msg.content),
                    created_at=_now_iso(),
                )
            )
    return records
