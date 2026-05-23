# FreightHero Watchtower — Agent Guide

Context for AI agents working in this repository. **Keep this file up to date** as the project evolves.

## Project summary

Take-home implementation of **FreightHero AI Watchtower**: a production-shaped agentic system for two freight workflows (ETA checkpoint, confirm delivery). It receives load events, tracking, inbound communications, and timers; runs SOP-driven agents with customer-specific rules; records mocked tool calls; and ships with evals, observability, and cloud deployment.

**Current state (Phase 1 complete):** uv project, `GET /health`, stub `LoadWorkflow` + worker, Docker/compose (Postgres + Temporal auto-setup), Terraform Temporal namespace + AWS skeleton. Phase 2+ (agent harness, write APIs, Langfuse) not started.

## Canonical documents

| Document | Role |
| --- | --- |
| [challenge-specs/README.md](challenge-specs/README.md) | Challenge requirements, API contract, rubric |
| [dos/research/implementation-spec.md](dos/research/implementation-spec.md) | **Single source of truth** for architecture and build details |
| [docs/BACKLOG.md](docs/BACKLOG.md) | Phased implementation checklist (what to build next) |
| [dos/research/use-temporal.md](dos/research/use-temporal.md) | Why Temporal replaced the initial pgmq/Supabase plan |
| [dos/research/initial-plan.md](dos/research/initial-plan.md) | Superseded plan (historical reference only) |

Challenge assets: `challenge-specs/assets/` (SOPs, schemas, fixtures, tools, customer expectations).

## Architecture (decided)

| Concern | Choice |
| --- | --- |
| Language / API | Python 3.12 + FastAPI |
| Packaging | [uv](https://docs.astral.sh/uv/) (`uv.lock`, `uv run`) |
| Durable async / per-load isolation | **Temporal Cloud** (`workflow_id = load-{load_id}`) |
| Agent runtime | LLM + SOP/customer config inside Temporal activities |
| AI tracing | **Langfuse** (OTel + `@observe` on activities) — Phase 2+ |
| Compute | AWS ECS Fargate (API + Worker from one image) |
| IaC | Terraform (`infra/`) — Temporal Cloud + AWS |
| Local dev | `docker-compose`, Makefile targets |

**Superseded:** initial-plan’s Supabase + pgmq + Railway stack. Do not reintroduce without an explicit decision.

## Conventions (Phase 1)

| Topic | Convention |
| --- | --- |
| Task queue | `freight-watchtower` |
| Config | `.env` for local app/worker; `infra/app-secrets.json` (gitignored) → Secrets Manager via TF; `terraform.tfvars` for non-secret TF inputs; shell env for TF providers |
| Run API | `make dev-api` or `uv run uvicorn app.api.main:app --reload --port 8000` |
| Run worker | `make dev-worker` or `uv run python -m app.worker` |
| Tests | `make test`; `pythonpath = ["."]` in `pyproject.toml` |
| Local Temporal | compose: `temporal:7233`, namespace `default`, no API key |

## Repository layout

```
app/               # FastAPI, worker, workflows, activities, tools (stubs)
evals/             # Eval harness stubs
infra/             # Terraform
docs/              # BACKLOG.md
challenge-specs/   # Read-only challenge inputs
```

## Agent workflow

### 1. Before each BACKLOG phase — grill the plan

Before implementing **any phase** in [docs/BACKLOG.md](docs/BACKLOG.md) (Phase 2, 3, …):

1. Apply the **grill-me** skill (`.cursor/skills/grill-me/SKILL.md`) or invoke `/grill-me`.
2. Stress-test that phase’s scope against [implementation-spec.md](dos/research/implementation-spec.md) and challenge requirements.

### 2. While implementing

- Follow [docs/BACKLOG.md](docs/BACKLOG.md) in order unless the user redirects.
- Match conventions in [implementation-spec.md](dos/research/implementation-spec.md).
- Use MCP when helpful: Temporal docs (`temporal-docs`), Terraform registry/plan (`terraform`).
- Minimize scope; avoid unrelated changes.
- Do not commit unless the user asks.

### 3. Always update this file

After meaningful progress, update **Current state**, **Conventions**, and **Gotchas**.

## Phase map (from BACKLOG)

| Phase | Focus | Status |
| --- | --- | --- |
| **1** | Repos, uv, FastAPI/Worker stubs, Docker, Terraform, README | Done |
| **2** | Agent harness: SOPs, schemas, tools, customers, evals, Langfuse | Next |
| **3** | First feature: `POST /loads`, inbound signal, evals 3b/3c | Planned |
| **4+** | Remaining fixtures | Planned |
| **Submission** | AWS deploy, eval evidence, `AI_USAGE.md`, `EVAL_REPORT.md` | Planned |

## Gotchas

- **Terraform vs `.env`:** Providers read shell env (`TEMPORAL_CLOUD_API_KEY`, `AWS_PROFILE`); app reads `.env` only. Never put Terraform account keys in Secrets Manager for the app.
- **Two Temporal keys:** `TEMPORAL_CLOUD_API_KEY` (account, Terraform); `TEMPORAL_API_KEY` (namespace, worker/API). Namespace key goes in `.env` locally and in Secrets Manager for ECS.
- **Secrets Manager:** Copy `infra/app-secrets.json.example` → `app-secrets.json`, fill, `terraform apply` (do not commit). Skips version if file missing. Values also land in `terraform.tfstate` — never commit state. Local dev uses `.env` only.
- **AWS profile:** Terraform does not use `~/.aws/credentials` unless `AWS_PROFILE` is set (or provider `profile` is configured).
- **Compose startup:** Temporal `auto-setup` may take ~30–60s before worker connects; retry worker if first connection fails.
- **Temporal namespace apply:** requires `terraform` CLI and `TEMPORAL_CLOUD_API_KEY`; not run in CI by default.
- **PowerShell terraform:** run `.\terraform.exe` from `infra/`; quote `-target="resource.name"`.
- **Security group descriptions:** AWS allows ASCII only (no em dashes in `description` fields).
- **`/health` + Temporal:** returns `temporal: unreachable` if server is down; still `status: ok`.

## Open / not yet built

- Write APIs, agent activities, SOP/customer YAML in app
- Langfuse wiring, `docs/ARCHITECTURE.md`, `docs/DEPLOYMENT.md`
- ECS task definitions/services, image push to ECR, populate Secrets Manager, deployed public URL
- `AI_USAGE.md`, full `evals/EVAL_REPORT.md`

---

*Last updated: Phase 1 complete; Terraform Temporal + AWS skeleton applied; Secrets Manager docs added.*
