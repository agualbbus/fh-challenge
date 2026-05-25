# Deployment

## Local development

1. `uv sync`
2. `docker compose up -d postgresql elasticmq`
3. Terminal A: `uv run uvicorn app.api.main:app --reload --port 8000`
4. Terminal B: `uv run python -m app.worker`
5. `uv run python evals/run_evals.py`

Copy `.env.example` → `.env`. Use `MODEL_MODE=mock` for evals without OpenRouter keys.

Or run the full stack: `docker compose up --build` (ensure `.dockerignore` excludes `.venv`).

## AWS (Terraform)

`infra/` provisions RDS PostgreSQL, SQS FIFO (+ DLQ), ECR, ECS cluster, ALB, Fargate API + worker services, and Secrets Manager.

1. Set `TF_VAR_db_password` (or in `terraform.tfvars`)
2. Copy `infra/app-secrets.json.example` → `infra/app-secrets.json` with `DATABASE_URL`, `SQS_QUEUE_URL`, `OPENROUTER_API_KEY`, `LANGSMITH_API_KEY`, `API_KEY`
3. Set `model_mode = "live"` in `terraform.tfvars` for production worker/API (default in `terraform.tfvars.example`)
4. `cd infra && terraform init && terraform apply`
5. Run one fixture against the public URL; save evidence under `docs/evidence/`

ECS services use `MODEL_MODE` from Terraform `var.model_mode` (default `live`). The worker also receives LangSmith tracing env vars; secrets stay in Secrets Manager.

## CI/CD (GitHub → CodePipeline → CodeBuild → ECR → ECS)

Optional Terraform in `infra/aws_cicd.tf`. Enable after base AWS stack exists.

### One-time setup

1. In AWS Console → **Developer Tools** → **Connections**, create a **GitHub** CodeStar connection and complete authorization.
2. Add to `infra/terraform.tfvars`:

   ```hcl
   enable_cicd             = true
   github_owner            = "your-org"
   github_repo             = "freight-hero"
   github_branch           = "main"
   codestar_connection_arn = "arn:aws:codestar-connections:..."
   ```

3. `terraform apply` creates the S3 artifact bucket, CodeBuild project, and CodePipeline (`Source` → `Build` → `DeployAPI` → `DeployWorker`).

### Deploy flow

- Push to `github_branch` → pipeline runs `buildspec.yml`:
  - `uv sync --frozen` + `uv run pytest`
  - Docker build and push to ECR (`CODEBUILD_RESOLVED_SOURCE_VERSION` and `latest`)
  - `imagedefinitions-api.json` / `imagedefinitions-worker.json` for ECS deploy actions
- CodePipeline updates **api** and **worker** ECS services (Terraform ignores `task_definition` on services after initial create).

### Observability

| Resource | Where to look |
| --- | --- |
| Pipeline status | CodePipeline console → `freight-watchtower-pipeline` (or `codepipeline_name` output) |
| Build logs | CodeBuild → project from `codebuild_project_name` output |
| Runtime logs | CloudWatch → `/ecs/freight-watchtower-api`, `/ecs/freight-watchtower-worker` |
| API health | `http://<alb_dns_name>/health` |

### Rollback

- **ECS:** In the service → **Deployments** → roll back to the previous task definition revision.
- **Image:** Re-run the pipeline from a known-good git commit, or manually push an older ECR tag and start a pipeline execution with that artifact.

## Secrets

Never commit `.env` or `infra/app-secrets.json`. Keys: `DATABASE_URL`, `SQS_QUEUE_URL`, `OPENROUTER_API_KEY`, `LANGSMITH_API_KEY`, `API_KEY` for live mode and API auth.
