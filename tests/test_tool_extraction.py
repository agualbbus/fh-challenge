"""tool_extraction.extract_tool_records edge cases."""

from __future__ import annotations

from langchain_core.messages import AIMessage, ToolMessage

from app.worker.tool_extraction import _coerce_result, extract_tool_records


def test_coerce_result_dict_passthrough() -> None:
    assert _coerce_result({"ok": True}) == {"ok": True}


def test_coerce_result_invalid_json_string() -> None:
    assert _coerce_result("not json") == {"result": "not json"}


def test_coerce_result_non_dict_non_string() -> None:
    assert _coerce_result(42) == {"result": 42}


def test_extract_tool_records_pairs_calls_with_results() -> None:
    messages = [
        AIMessage(
            content="",
            tool_calls=[
                {"name": "send_sms", "args": {"x": 1}, "id": "tc-1", "type": "tool_call"}
            ],
        ),
        ToolMessage(content='{"ok": true}', tool_call_id="tc-1"),
    ]
    records = extract_tool_records(messages, load_id="L1", event_id="E1")
    assert len(records) == 1
    rec = records[0]
    assert rec.tool == "send_sms"
    assert rec.arguments == {"x": 1}
    assert rec.result == {"ok": True}
    assert rec.load_id == "L1"
    assert rec.event_id == "E1"


def test_extract_tool_records_handles_unmatched_tool_message() -> None:
    messages = [ToolMessage(content="orphan", tool_call_id="missing")]
    records = extract_tool_records(messages, load_id="L1", event_id="E1")
    assert len(records) == 1
    assert records[0].tool == ""
