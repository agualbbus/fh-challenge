"""Panic-button reset for eval state: Postgres checkpoints + ElasticMQ dedup.

With per-run `load_id` suffixes in `run_evals.py`, this script is rarely
needed — historical loads age out naturally — but it's the documented
recovery path when a stuck checkpoint or FIFO dedup window bites.
"""

from __future__ import annotations

import os
import subprocess
import sys

import psycopg

from app.config import get_settings


_PURGE_SQL = """
DELETE FROM checkpoints WHERE thread_id LIKE 'load-eval-%';
DELETE FROM checkpoint_blobs WHERE thread_id LIKE 'load-eval-%';
DELETE FROM checkpoint_writes WHERE thread_id LIKE 'load-eval-%';
"""


def _purge_postgres(database_url: str) -> None:
    with psycopg.connect(database_url) as conn, conn.cursor() as cur:
        cur.execute(_PURGE_SQL)
    print("Postgres: purged eval checkpoints", file=sys.stderr)


def _restart_elasticmq() -> None:
    # ElasticMQ holds the FIFO dedup window in-process; restart drops it.
    # Falls back to a no-op on hosts where docker compose isn't reachable.
    try:
        subprocess.run(
            ["docker", "compose", "restart", "elasticmq"],
            check=True,
            capture_output=True,
        )
        print("ElasticMQ: restarted", file=sys.stderr)
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        print(f"ElasticMQ restart skipped: {exc}", file=sys.stderr)


def main() -> int:
    settings = get_settings()
    _purge_postgres(settings.database_url)
    if os.environ.get("SKIP_ELASTICMQ_RESET") != "1":
        _restart_elasticmq()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
