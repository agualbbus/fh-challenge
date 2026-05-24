"""Work item envelope for SQS FIFO."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from typing import Any


@dataclass
class WorkMessage:
    load_id: str
    kind: str
    payload: dict[str, Any]
    dedup_id: str

    def to_json(self) -> str:
        return json.dumps(
            {
                "load_id": self.load_id,
                "kind": self.kind,
                "payload": self.payload,
                "dedup_id": self.dedup_id,
            }
        )

    @classmethod
    def from_json(cls, body: str) -> WorkMessage:
        data = json.loads(body)
        return cls(
            load_id=data["load_id"],
            kind=data["kind"],
            payload=data["payload"],
            dedup_id=data.get("dedup_id", str(uuid.uuid4())),
        )


def dedup_id_for_seed(load_id: str) -> str:
    return f"seed-{load_id}"


def dedup_id_for_event(event: dict[str, Any]) -> str:
    return event.get("event_id") or str(uuid.uuid4())


def dedup_id_for_task(task: dict[str, Any]) -> str:
    return task.get("task_uuid") or str(uuid.uuid4())


def dedup_id_for_timer(timer_id: str) -> str:
    return f"timer-{timer_id}"
