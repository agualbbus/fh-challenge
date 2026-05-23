"""Per-load durable workflow (stub — Phase 1)."""

from __future__ import annotations

from typing import Any

from temporalio import workflow


@workflow.defn
class LoadWorkflow:
    """One workflow per load_id; serializes all events for that load."""

    def __init__(self) -> None:
        self.load_state: dict[str, Any] = {}
        self.session: dict[str, Any] = {}
        self._events: list[dict[str, Any]] = []
        self._tasks: list[dict[str, Any]] = []

    @workflow.query
    def get_state(self) -> dict[str, Any]:
        return {
            "load_state": self.load_state,
            "session": self.session,
            "events": list(self._events),
            "tasks": list(self._tasks),
        }

    @workflow.signal
    async def on_event(self, event: dict[str, Any]) -> None:
        self._events.append(event)

    @workflow.signal
    async def on_task(self, task: dict[str, Any]) -> None:
        self._tasks.append(task)

    @workflow.run
    async def run(self, load_id: str, seed: dict[str, Any] | None = None) -> None:
        self.load_state = {"load_id": load_id}
        if seed:
            self.load_state.update(seed)
        await workflow.wait_condition(lambda: False)
