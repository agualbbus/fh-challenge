"""Entrypoint: `python -m app.worker`."""

from app.asyncio_compat import run as run_async
from app.worker.main import main

if __name__ == "__main__":
    run_async(main())
