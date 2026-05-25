"""asyncio_compat.run wrapper."""

from __future__ import annotations

from app.asyncio_compat import run


async def _coro() -> int:
    return 42


def test_run_executes_coroutine() -> None:
    assert run(_coro()) == 42
