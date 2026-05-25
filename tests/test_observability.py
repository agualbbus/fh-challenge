"""Structured logging helper."""

from __future__ import annotations

import json
import logging

from app.observability.logging import log_event


def test_log_event_emits_json(caplog) -> None:
    with caplog.at_level(logging.INFO, logger="watchtower"):
        log_event("hello", load_id="L1", count=2)
    record = caplog.records[-1]
    payload = json.loads(record.message)
    assert payload == {"message": "hello", "load_id": "L1", "count": 2}
