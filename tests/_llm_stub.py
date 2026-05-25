"""Test-only scripted chat model. Not used in production."""

from __future__ import annotations

import uuid
from typing import Any

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import PrivateAttr
from typing_extensions import override


class ScriptedChatModel(BaseChatModel):
    """Yields a fixed sequence of AIMessages in order; ignores its inputs."""

    responses: list[AIMessage]
    _index: int = PrivateAttr(default=0)

    def bind_tools(self, tools, *, tool_choice=None, **kwargs):  # noqa: ANN001
        return self

    @property
    @override
    def _llm_type(self) -> str:
        return "test-scripted"

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


def tool_call(name: str, args: dict[str, Any]) -> dict[str, Any]:
    return {"name": name, "args": args, "id": str(uuid.uuid4()), "type": "tool_call"}
