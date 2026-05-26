"""PostgreSQL checkpointer lifecycle for LangGraph."""

from __future__ import annotations

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

_checkpointer: AsyncPostgresSaver | None = None
_pool: AsyncConnectionPool | None = None


async def init_checkpointer(database_url: str) -> AsyncPostgresSaver:
    """Open a pooled checkpointer and run migrations once per process.

    Uses ``AsyncConnectionPool`` instead of a single connection so concurrent
    graph invocations (parallel SQS handlers, parallel eval reads) don't race
    on one psycopg connection.
    """
    global _checkpointer, _pool
    if _checkpointer is not None:
        return _checkpointer

    _pool = AsyncConnectionPool(
        conninfo=database_url,
        max_size=20,
        kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
        open=False,
    )
    await _pool.open()
    _checkpointer = AsyncPostgresSaver(conn=_pool)
    await _checkpointer.setup()
    return _checkpointer


def get_checkpointer() -> AsyncPostgresSaver:
    if _checkpointer is None:
        raise RuntimeError("Checkpointer not initialized; call init_checkpointer() first")
    return _checkpointer


async def close_checkpointer() -> None:
    global _checkpointer, _pool
    if _pool is not None:
        await _pool.close()
    _checkpointer = None
    _pool = None
