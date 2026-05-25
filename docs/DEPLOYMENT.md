# Deployment

## Local development

1. `uv sync`
2. `docker compose up -d postgresql elasticmq`
3. Terminal A: `uv run uvicorn app.api.main:app --reload --port 8000`
4. Terminal B: `uv run python -m app.worker`
5. `uv run python evals/run_evals.py`

Copy `.env.example` → `.env`. Use `MODEL_MODE=mock` for evals without OpenRouter keys.

Or run the full stack: `docker compose up --build` (ensure `.dockerignore` excludes `.venv`).

## AWS

`infra/` provisions RDS PostgreSQL, SQS FIFO (+ DLQ), ECR, ECS cluster, ALB, Secrets Manager, and a GitHub OIDC deploy role.

1. Set `TF_VAR_db_password` (or in `terraform.tfvars`)
2. Copy `infra/app-secrets.json.example` → `infra/app-secrets.json` with `DATABASE_URL`, `SQS_QUEUE_URL`, `OPENROUTER_API_KEY`, `LANGSMITH_API_KEY`, `API_KEY`
3. `terraform apply`
4. Copy Terraform output `github_deploy_role_arn` into GitHub repo secret `AWS_DEPLOY_ROLE_ARN`
5. Test CI on branch `github-ecs-setup` (see below), then merge to `main` for production rollouts
6. Run one fixture against the public URL; save evidence under `docs/evidence/`

### CI/CD (GitHub Actions)

Workflow: [`.github/workflows/deploy.yml`](../.github/workflows/deploy.yml)

**One-time setup:** after `terraform apply`, set GitHub secret `AWS_DEPLOY_ROLE_ARN` from `terraform output -raw github_deploy_role_arn`. OIDC trust allows `github-ecs-setup` and `main` (see `var.github_deploy_branches`).

**Test branch (`github-ecs-setup`)** — push builds and pushes `freight-watchtower:<sha>` only (validates OIDC + ECR; does not update `:latest` or roll ECS).

**Full deploy** — either push to `main`, or run **deploy** manually on `github-ecs-setup` with `deploy_ecs=true` (pushes `:latest` and force-deploys both services).

**Production (`main`)** — every push:

1. Assume the AWS deploy role via OIDC
2. Build and push `freight-watchtower:<sha>` and `freight-watchtower:latest`
3. `force-new-deployment` on API and worker
4. Wait until both services are stable

### Manual deploy

Fallback when GitHub Actions is unavailable:

```bash
AWS_REGION=us-east-1
ECR_REPO=freight-watchtower
ECS_CLUSTER=freight-watchtower
REGISTRY=$(aws ecr describe-repositories --repository-names $ECR_REPO --query 'repositories[0].repositoryUri' --output text | sed 's|/.*||')
IMAGE=$REGISTRY/$ECR_REPO

aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $REGISTRY
docker build -t $IMAGE:latest .
docker push $IMAGE:latest

aws ecs update-service --cluster $ECS_CLUSTER --service freight-watchtower-api --force-new-deployment
aws ecs update-service --cluster $ECS_CLUSTER --service freight-watchtower-worker --force-new-deployment
aws ecs wait services-stable --cluster $ECS_CLUSTER \
  --services freight-watchtower-api freight-watchtower-worker
```

## Secrets

Never commit `.env` or `infra/app-secrets.json`. Keys: `DATABASE_URL`, `SQS_QUEUE_URL`, `API_KEY`, optional `OPENROUTER_API_KEY`, `LANGSMITH_API_KEY` for live tracing.

## Post-deploy verification

1. `aws ecs describe-services --cluster freight-watchtower --services freight-watchtower-api freight-watchtower-worker` — confirm rollout completed
2. `curl http://$(cd infra && terraform output -raw alb_dns_name)/health`
3. Run one fixture against the deployed URL; archive output under `docs/evidence/`
