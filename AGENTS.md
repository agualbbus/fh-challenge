# AGENTS.md

## Cursor Cloud specific instructions

### Services overview

This project has four runtime components for local dev:

| Service | How to start | Port |
|---|---|---|
| PostgreSQL 16 | `docker compose up -d postgresql` | 5432 |
| ElasticMQ (local SQS) | `docker compose up -d elasticmq` | 9324, 9325 |
| FastAPI (API) | `uv run uvicorn app.api.main:app --reload --port 8000` | 8000 |
| Worker (SQS consumer) | `uv run python -m app.worker` | — |

### Quick reference

- **Install deps:** `uv sync`
- **Lint:** `uv run ruff check .` and `uv run ruff format --check .`
- **Tests:** `uv run pytest` (uses in-memory mocks; no Postgres/SQS/LLM key needed)
- **Full local stack:** see `README.md` "Quick start (local)" section
- **Makefile targets:** `make install`, `make test`, `make dev-api`, `make dev-worker`, `make lint-fix`

### Non-obvious gotchas

- **Docker in Cloud Agent VMs** requires `fuse-overlayfs`, `iptables-legacy`, and the `"storage-driver": "fuse-overlayfs"` daemon config. The dockerd must be started with `sudo` before `docker compose up`.
- **`.env` for host-mode dev** must uncomment `DATABASE_URL`, `SQS_QUEUE_URL`, `AWS_ENDPOINT_URL`, `AWS_REGION`, and the dummy `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` lines. Without these, the API/worker can't reach the local Postgres and ElasticMQ containers. Copy from `.env.example` and adjust.
- **Auth is disabled** in local dev when `API_KEY` env var is unset — write endpoints accept requests without an `X-API-Key` header.
- **Worker will error on LLM calls** without a real `OPENROUTER_API_KEY`. Unit tests mock the LLM via `ScriptedChatModel` and don't need it. Only evals and live agent runs require a real key.
- **`uv` must be on PATH** — installed to `$HOME/.local/bin`. Add `export PATH="$HOME/.local/bin:$PATH"` if `uv` is not found.
- **Postgres healthcheck** takes ~10s after container start; wait for `service_healthy` before starting API/worker.
