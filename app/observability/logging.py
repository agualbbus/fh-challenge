"""Structured JSON logging helpers."""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger("watchtower")


def log_event(message: str, **fields: Any) -> None:
    payload = {"message": message, **fields}
    logger.info(json.dumps(payload, default=str))
