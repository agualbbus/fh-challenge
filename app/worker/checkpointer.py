"""PostgreSQL checkpointer lifecycle for LangGraph."""

from __future__ import annotations

from typing import TYPE_CHECKING

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

_checkpointer: AsyncPostgresSaver | None = None
_context: AsyncIterator[AsyncPostgresSaver] | None = None


async def init_checkpointer(database_url: str) -> AsyncPostgresSaver:
    """Open checkpointer pool and run migrations once per process."""
    global _checkpointer, _context
    if _checkpointer is not None:
        return _checkpointer

    _context = AsyncPostgresSaver.from_conn_string(database_url)
    _checkpointer = await _context.__aenter__()
    await _checkpointer.setup()
    return _checkpointer


def get_checkpointer() -> AsyncPostgresSaver:
    if _checkpointer is None:
        raise RuntimeError("Checkpointer not initialized; call init_checkpointer() first")
    return _checkpointer


async def close_checkpointer() -> None:
    global _checkpointer, _context
    if _context is not None:
        await _context.__aexit__(None, None, None)
    _checkpointer = None
    _context = None
