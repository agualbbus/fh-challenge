# FreightHero Watchtower

Production-shaped take-home: SOP-driven freight agents on **LangGraph**, **SQS FIFO**, and **PostgreSQL**, with FastAPI ingress and AWS ECS deployment (Phase 4+).

## Prerequisites

- [uv](https://docs.astral.sh/uv/) (Python 3.12)
- [Docker](https://www.docker.com/) (for compose stack)
- [Terraform](https://developer.hashicorp.com/terraform/install) >= 1.5 (for `infra/`)

## Quick start (local)

```bash
uv sync
make test          # or: uv run pytest
```

**API + worker on host** (requires Postgres + ElasticMQ):

```bash
docker compose up postgresql elasticmq -d
make dev-api       # terminal 1
make dev-worker    # terminal 2
curl http://localhost:8000/health
```

**Full stack local development in Docker:**

For the dockerized stack, the only env vars you need in `.env` are the LLM and (optional) tracing credentials — Compose injects the container-internal `DATABASE_URL`, `SQS_QUEUE_URL`, and AWS endpoint values for you. Create a `.env` with:

```bash
# required
OPENROUTER_API_KEY=sk-or-...

# optional — enable LangSmith tracing
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=lsv2_...
LANGSMITH_PROJECT=fh-dev
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
```

Leave any `DATABASE_URL` / `SQS_QUEUE_URL` / `AWS_*` lines commented out — they target `localhost` and would conflict with the container network. Then:

```bash
docker compose up --build
curl http://localhost:8000/health
```

- API: http://localhost:8000
- Postgres: `localhost:5432` (db `watchtower`)
- ElasticMQ: http://localhost:9324

See [`.env.example`](.env.example) for the full list of supported overrides (used when running the API/worker on the host instead of in containers).

Agent runs use **[OpenRouter](https://openrouter.ai/)** via `langchain-openrouter` (`OPENROUTER_API_KEY`) — see [implementation-spec §2.9](docs/research/implementation-spec.md). Tests stub the chat model via the `app.worker.llm.get_chat_model` seam (no LLM mock module).

## Configuration

| File / store | Purpose |
| --- | --- |
| `.env` | App/worker locally (gitignored) — see `.env.example` |
| `infra/terraform.tfvars` | Non-secret Terraform inputs |
| `infra/app-secrets.json` | ECS secrets (gitignored); Terraform syncs to Secrets Manager |

## Terraform

```bash
cd infra
terraform init
terraform apply
```

See [infra/README.md](infra/README.md) for RDS, SQS, and Secrets Manager.

## Makefile

## Makefile

| Target | Description |
| --- | --- |
| `make install` | `uv sync` |
| `make dev-api` | FastAPI on :8000 |
| `make dev-worker` | SQS consumer + LangGraph worker |
| `make test` | `pytest` |
| `make eval` | Fixture harness (`3b`, `3c`) |

## Layout

```
app/api/          FastAPI routes (SQS publish)
app/worker/       SQS worker, LangGraph, create_agent, router
app/queue/        SQS publisher / consumer
app/tools/        Mocked tool registry
evals/            Fixture harness
infra/            Terraform — RDS, SQS, ECS skeleton
docs/             Architecture, deployment, implementation spec
```

## Docs

- [Implementation spec](docs/research/implementation-spec.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Challenge requirements](challenge-specs/README.md)
