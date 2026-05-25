"""Platform-specific asyncio helpers."""

from __future__ import annotations

import asyncio
import sys
from collections.abc import Coroutine
from typing import Any


def run[T](coro: Coroutine[Any, Any, T]) -> T:
    """Run an async coroutine with a psycopg-compatible event loop on Windows."""
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    return asyncio.run(coro)
