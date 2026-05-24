# FreightHero Watchtower — Agent Guide

Context for AI agents working in this repository. **Keep this file up to date** as the project evolves.

## Project summary

Take-home implementation of **FreightHero AI Watchtower**: SOP-driven agents for ETA checkpoint and confirm delivery workflows, with LangGraph + SQS + PostgreSQL, declarative customer config, mocked recorded tools, and fixture evals.

**Current state:** Five write APIs (`202`), SQS FIFO ingress, LangGraph per-load graph with Postgres checkpoints, LangChain `create_agent`, HTTP eval harness for `3b`/`3c`. LangSmith optional via env vars (`LANGCHAIN_TRACING_V2=false` by default). Phase 4+ fixtures and ECS deploy pending.

## Canonical documents

| Document | Role |
| --- | --- |
| [challenge-specs/README.md](challenge-specs/README.md) | Challenge requirements, API contract, rubric |
| [docs/research/implementation-spec.md](docs/research/implementation-spec.md) | **Single source of truth** for architecture |
| [docs/BACKLOG.md](docs/BACKLOG.md) | Phased checklist |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | System design write-up |
| [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) | Local + cloud deploy notes |

## Architecture (decided)

| Concern | Choice |
| --- | --- |
| Language / API | Python 3.12 + FastAPI |
| Packaging | [uv](https://docs.astral.sh/uv/) |
| Queue | **AWS SQS FIFO** (`MessageGroupId = load_id`) |
| Agent / orchestration | **LangGraph** + **LangChain `create_agent`** + durable execution (`@task`) |
| Persistence | **PostgreSQL** (`AsyncPostgresSaver`) |
| LLM | **ChatOpenRouter** via `langchain-openrouter` (live); fixture mock LLM (CI) |
| Tracing | **LangSmith** (optional) |
| Local stack | `docker compose` → Postgres + ElasticMQ + API + worker |

## Grill decisions (locked)

| Topic | Choice |
| --- | --- |
| Per-load ID | `thread_id = load-{load_id}` |
| API → agent | SQS publish only; API never invokes graph |
| `MODEL_MODE=mock` | Fake LLM (`MockToolCallingModel`) emits fixture tool calls — no OpenRouter |
| Broker ignore | Pre-agent guard in orchestrator; event still accepted (`202`) |
| State merge | Graph node applies `AgentDecision` to checkpoint state |
| API responses | `202` with `{accepted, load_id, workflow_id}` |

## Conventions

| Topic | Convention |
| --- | --- |
| SQS queue | `freight-watchtower.fifo` (local: ElasticMQ) |
| Run API | `uv run uvicorn app.api.main:app --reload --port 8000` |
| Run worker | `uv run python -m app.worker` |
| Evals | `uv run python evals/run_evals.py` (needs API + worker + Postgres + SQS) |
| Tests | `uv run pytest` |
| Customer config | `CustomerProfile` from YAML — no scattered `if customer_id` |

## Phase map

| Phase | Status |
| --- | --- |
| **1** Repos, uv, Docker, Terraform skeleton | Done |
| **2** Agent harness (tools, customers, evals, LangSmith stub) | Done |
| **3** `3b` / `3c` via `create_agent` + write APIs | Done |
| **4+** Remaining visible fixtures | Planned |
| **Submission** | AWS deploy, evidence, `AI_USAGE.md` | Planned |

## Gotchas

- Wrap side effects (agent + tools) in LangGraph `@task` for durable replay.
- `.dockerignore` excludes `.venv` — required for reasonable image builds.
- Eval harness uses `graph.aget_state`; no read HTTP API.
- SQS max delay 900s — use EventBridge for longer ETA follow-ups in production.

---

*Last updated: consolidated worker package (`app/worker/`).*
