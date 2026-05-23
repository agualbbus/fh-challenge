# FreightHero Watchtower

Production-shaped take-home: SOP-driven freight agents on **Temporal Cloud**, FastAPI ingress, AWS ECS deployment (Phase 4+).

## Prerequisites

- [uv](https://docs.astral.sh/uv/) (Python 3.12)
- [Docker](https://www.docker.com/) (for compose stack)
- [Terraform](https://developer.hashicorp.com/terraform/install) >= 1.5 (for `infra/`)
- Temporal Cloud account (for namespace apply) — see [infra/README.md](infra/README.md)

## Quick start (local)

Local Temporal uses **Docker Compose** (`temporalio/auto-setup`), not `temporal server start-dev`.

```bash
uv sync
make test          # or: uv run pytest
```

**API + worker on host** (requires Temporal at `localhost:7233`):

```bash
docker compose up postgresql temporal temporal-ui -d
make dev-api       # terminal 1 — or: uv run uvicorn app.api.main:app --reload --port 8000
make dev-worker    # terminal 2 — or: uv run python -m app.worker
curl http://localhost:8000/health
```

On Windows, `make` is optional if `uv` is on your PATH (install [GnuWin32 Make](http://gnuwin32.sourceforge.net/packages/make.htm) or use the `uv run` commands above).

**Full stack in Docker:**

```bash
docker compose up --build
curl http://localhost:8000/health
```

- API: http://localhost:8000
- Temporal Web UI: http://localhost:8233
- Task queue: `freight-watchtower`

Copy [`.env.example`](.env.example) to `.env` for overrides (optional for local compose; required for Temporal Cloud).

Live agent runs use **[OpenRouter](https://openrouter.ai/)** as the LLM provider (`OPENROUTER_API_KEY`, OpenAI-compatible API). CI/evals use `MODEL_MODE=mock` without an API key — see [implementation-spec §2.9](docs/research/implementation-spec.md#29-llm-provider--openrouter).

## Configuration

| File / store | Purpose |
| --- | --- |
| `.env` | App/worker locally (gitignored) — see `.env.example` |
| `infra/terraform.tfvars` | Non-secret Terraform inputs |
| Shell env | `TEMPORAL_CLOUD_API_KEY`, `AWS_PROFILE` for Terraform |
| `infra/app-secrets.json` | ECS secrets (gitignored); Terraform syncs to Secrets Manager |

Terraform does **not** read `.env`. The app does **not** read Secrets Manager locally.

### Secrets (local vs AWS)

- **Local dev:** copy [`.env.example`](.env.example) → `.env`. Use a Temporal Cloud **namespace** API key as `TEMPORAL_API_KEY` when connecting to cloud (not the account key used for Terraform).
- **ECS deploy:** copy `infra/app-secrets.json.example` → `infra/app-secrets.json`, fill values, `terraform apply`. Full steps: [infra/README.md](infra/README.md#secrets-aws-secrets-manager).

## Terraform

```bash
cd infra
# export TEMPORAL_CLOUD_API_KEY and AWS_PROFILE in your shell first
terraform init
terraform apply
```

Namespace-only apply: `terraform apply -target="temporalcloud_namespace.fh"` (quote the target on PowerShell).

See [infra/README.md](infra/README.md) for Temporal namespace setup, AWS skeleton outputs, and Secrets Manager.

## Makefile

| Target | Description |
| --- | --- |
| `make install` | `uv sync` |
| `make dev-api` | FastAPI with reload on :8000 |
| `make dev-worker` | Temporal worker |
| `make test` | pytest |
| `make eval` | Eval harness (Phase 2+) |

## Project layout

```
app/              FastAPI, worker, workflows, activities (stubs)
evals/            Fixture eval harness (Phase 2+)
infra/            Terraform — Temporal Cloud + AWS ECS skeleton
challenge-specs/  Challenge inputs (read-only)
docs/BACKLOG.md   Implementation phases
```

## Docs

- [Implementation backlog](docs/BACKLOG.md)
- [Implementation spec](docs/research/implementation-spec.md)
- [Agent guide](AGENTS.md)
