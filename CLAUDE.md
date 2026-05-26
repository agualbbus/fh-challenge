# FreightHero Watchtower — Agent Guide

Context for AI agents working in this repository. **Keep this file up to date** as the project evolves.

## Project summary

Take-home implementation of **FreightHero AI Watchtower**: SOP-driven agents for ETA checkpoint and confirm delivery workflows, with LangGraph + SQS + PostgreSQL, declarative customer config, mocked recorded tools, and fixture evals.

**Current state:** Five write APIs (`202`), SQS FIFO ingress, LangGraph per-load graph with Postgres checkpoints, LangChain `create_agent`, HTTP eval harness for `3b`/`3c`. LangSmith optional via env vars (`LANGSMITH_TRACING=false` by default; ECS worker also sets legacy `LANGCHAIN_*` aliases). AWS ECS/ALB/RDS/SQS via Terraform; `main` deploys via GitHub Actions OIDC → ECR → ECS force deploy. Phase 4+ fixtures pending.

## Canonical documents

| Document | Role |
| --- | --- |
| [challenge-specs/README.md](challenge-specs/README.md) | Challenge requirements, API contract |
| [challenge-specs/assets/rubric.md](challenge-specs/assets/rubric.md) | Submission scoring and review expectations |
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
| Lint | `uv run ruff check .` and `uv run ruff format --check .` |
| PR CI | `.github/workflows/ci.yml` — ruff + pytest on every pull request |
| Customer config | `CustomerProfile` from YAML — no scattered `if customer_id` |
| Cloud deploy | Push to `main` → GitHub Actions OIDC → ECR `:sha`/`:latest` → ECS `force-new-deployment` (not CodePipeline) |

## Phase map

| Phase | Status |
| --- | --- |
| **1** Repos, uv, Docker, Terraform skeleton | Done |
| **2** Agent harness (tools, customers, evals, LangSmith stub) | Done |
| **3** `3b` / `3c` via `create_agent` + write APIs | Done |
| **4+** Remaining visible fixtures | Done |
| **Submission** | Live evidence, `AI_USAGE.md` | Planned |

## Gotchas

- Wrap side effects (agent + tools) in LangGraph `@task` for durable replay.
- `.dockerignore` excludes `.venv` — required for reasonable image builds.
- Eval harness uses `graph.aget_state`; no read HTTP API.
- SQS max delay 900s — use EventBridge for longer ETA follow-ups in production.
- Tracking pings are handled deterministically in `app/worker/tracking.py` (no LLM) — three consecutive in-geofence pings trigger `at_delivery` transition via synthetic `ToolCallRecord`s appended to the checkpoint.
- Attachment-driven SOP switch: when an inbound_communication with attachments arrives on the `delivery_eta_checkpoint` SOP, `event_node` promotes `active_task` to `confirm_delivery` before invoking the agent so `check_attachment` is available.

## Keep CLAUDE.md files in sync

**Whenever you change code, also update any `CLAUDE.md` it describes — in the same change, before declaring the task done.** These files are the agent contract for the project; stale guidance is worse than no guidance.

Triggers that require a doc update:

- Adding, removing, renaming, splitting, or merging a module that appears in a Module Map.
- Changing routing edges, graph nodes, checkpoint state fields, or any flow shown in a mermaid diagram.
- Renaming public functions or moving them between modules (cross-check Module Map rows and prose references).
- Changing run commands, environment variables, or local-stack requirements.
- Adding a new fixture branch, customer-profile flag, SOP section, or mock-model rule (live + mock paths must stay parallel).
- Changing layer boundaries (e.g., what belongs in `app/queue/` vs `app/worker/`).

Where to update:

- Root [`CLAUDE.md`](CLAUDE.md) — architecture-wide decisions, conventions, phase map.
- Per-module `CLAUDE.md` (e.g. [`app/worker/CLAUDE.md`](app/worker/CLAUDE.md)) — module map, internal flows, gotchas. Each module's "Keep In Sync" section lists its triggers.
- If a change touches both scopes, update both.

After editing, re-read the updated section end-to-end to confirm every named symbol and every mermaid node still matches the code.
