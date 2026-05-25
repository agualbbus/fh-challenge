# Deployment

## Local development

1. `uv sync`
2. `docker compose up -d postgresql elasticmq`
3. Terminal A: `uv run uvicorn app.api.main:app --reload --port 8000`
4. Terminal B: `uv run python -m app.worker`
5. `uv run python evals/run_evals.py`

Copy `.env.example` → `.env` and set `OPENROUTER_API_KEY` — the agent path always calls OpenRouter.

Or run the full stack: `docker compose up --build` (ensure `.dockerignore` excludes `.venv`).

## AWS

`infra/` provisions RDS PostgreSQL, SQS FIFO (+ DLQ), ECR, ECS cluster, ALB, and Secrets Manager.

1. Set `TF_VAR_db_password` (or in `terraform.tfvars`)
2. Copy `infra/app-secrets.json.example` → `infra/app-secrets.json` with `DATABASE_URL`, `SQS_QUEUE_URL`, `OPENROUTER_API_KEY`, `LANGSMITH_API_KEY`
3. `terraform apply`
4. `docker build -t watchtower .` and push to ECR
5. Run one fixture against the public URL; save evidence under `docs/evidence/`

## Secrets

Never commit `.env` or `infra/app-secrets.json`. Keys: `DATABASE_URL`, `SQS_QUEUE_URL`, optional `OPENROUTER_API_KEY`, `LANGSMITH_API_KEY` for live tracing.
