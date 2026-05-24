"""Fixture-driven mock LLM for deterministic MODEL_MODE=mock evals."""

from __future__ import annotations

import uuid
from typing import Any, Iterator

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import PrivateAttr
from typing_extensions import override

from app.customers.base import get_customer_profile
from app.worker.load_data import detect_requested_field, get_load_field


class MockToolCallingModel(BaseChatModel):
    """Fake chat model for create_agent; uses `responses`, not `messages` (name clash)."""

    responses: list[AIMessage]
    _index: int = PrivateAttr(default=0)

    def bind_tools(self, tools, *, tool_choice=None, **kwargs):  # noqa: ANN001
        return self

    @property
    @override
    def _llm_type(self) -> str:
        return "mock-tool-calling"

    @override
    def _generate(
        self,
        messages: list,
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        del messages, stop, run_manager, kwargs
        if self._index >= len(self.responses):
            msg = AIMessage(content="Done.")
        else:
            msg = self.responses[self._index]
            self._index += 1
        return ChatResult(generations=[ChatGeneration(message=msg)])


def _tool_call(name: str, args: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": name,
        "args": args,
        "id": str(uuid.uuid4()),
        "type": "tool_call",
    }


def _sender_type(event: dict[str, Any]) -> str | None:
    if event.get("event_type") != "inbound_communication":
        return None
    return event.get("inbound_communication", {}).get("sender_type")


def _content(event: dict[str, Any]) -> str:
    if event.get("event_type") != "inbound_communication":
        return ""
    return event.get("inbound_communication", {}).get("content", "")


def _channel(event: dict[str, Any]) -> str:
    if event.get("event_type") != "inbound_communication":
        return "sms"
    return event.get("inbound_communication", {}).get("channel", "sms")


def _is_load_info_question(content: str) -> bool:
    text = content.lower()
    keywords = (
        "address",
        "phone",
        "receiver",
        "reference",
        "appointment",
        "delivery number",
        "pickup number",
        "load info",
        "where am i going",
        "where do i deliver",
    )
    return any(k in text for k in keywords)


def _is_operational_issue(content: str) -> bool:
    text = content.lower()
    keywords = ("broke down", "breakdown", "accident", "flat tire", "damage", "blocked", "broke")
    return any(k in text for k in keywords)


def build_mock_responses(
    load_state: dict[str, Any],
    event: dict[str, Any],
) -> Iterator[AIMessage]:
    """Map event + load_state to ordered AIMessages for the mock agent loop."""
    sender = _sender_type(event)
    if sender == "broker":
        yield AIMessage(content="Broker message ignored.")
        return

    if event.get("event_type") != "inbound_communication":
        yield AIMessage(content="No action for this event type.")
        return

    content = _content(event)
    channel = _channel(event)
    task = load_state.get("active_task") or "delivery_eta_checkpoint"
    customer_id = load_state.get("customer_id", "customer_a")
    load_data = load_state.get("load_data", {})

    if _is_load_info_question(content):
        field = detect_requested_field(content)
        value = get_load_field(load_data, field)
        tool_calls: list[dict[str, Any]] = [
            _tool_call("get_load_info", {"field": field}),
        ]

        if value:
            if channel == "sms":
                tool_calls.append(
                    _tool_call("send_sms", {"recipient": "driver", "message": value})
                )
            else:
                tool_calls.append(
                    _tool_call(
                        "send_email",
                        {
                            "recipient": "driver",
                            "subject": "Load information",
                            "body": value,
                        },
                    )
                )
        else:
            profile = get_customer_profile(customer_id)
            if channel == "sms":
                tool_calls.append(
                    _tool_call(
                        "send_sms",
                        {
                            "recipient": "driver",
                            "message": "We're checking on that and will get back to you shortly.",
                        },
                    )
                )
            if profile.missing_load_info.create_task:
                tool_calls.append(
                    _tool_call(
                        "create_task",
                        {
                            "title": f"Missing load info: {field}",
                            "description": f"Driver asked for {field} which is not in load data.",
                            "task_type": "missing_load_info",
                        },
                    )
                )
            if profile.missing_load_info.notify_slack:
                tool_calls.append(
                    _tool_call(
                        "send_slack_message",
                        {
                            "audience": profile.missing_load_info.slack_audience,
                            "message": f"Missing load info requested by driver: {field}",
                            "escalation_type": "missing_load_info",
                        },
                    )
                )

        yield AIMessage(content="", tool_calls=tool_calls)
        yield AIMessage(content="Load info question handled.")
        return

    if _is_operational_issue(content) and task == "delivery_eta_checkpoint":
        tool_calls = [
            _tool_call(
                "create_issue",
                {
                    "title": "Operational issue reported",
                    "description": content,
                    "issue_type": "equipment_failure"
                    if "broke" in content.lower() or "breakdown" in content.lower()
                    else "other",
                },
            ),
        ]
        if channel == "sms":
            tool_calls.append(
                _tool_call(
                    "send_sms",
                    {
                        "recipient": "driver",
                        "message": "Thanks — the team will review this shortly.",
                    },
                )
            )
        yield AIMessage(content="", tool_calls=tool_calls)
        yield AIMessage(content="Operational issue handled.")
        return

    yield AIMessage(content="No matching action.")


def build_mock_model(
    load_state: dict[str, Any],
    event: dict[str, Any],
) -> MockToolCallingModel:
    return MockToolCallingModel(responses=list(build_mock_responses(load_state, event)))
