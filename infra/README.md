# Infrastructure (Terraform)

## Prerequisites

- [Terraform](https://developer.hashicorp.com/terraform/install) >= 1.5
- AWS account with credentials (`AWS_PROFILE` or `AWS_*`)

## Config split

| Source | Purpose |
| --- | --- |
| Shell env `AWS_PROFILE` or `AWS_*` | Terraform `aws` provider |
| `terraform.tfvars` | Non-secret inputs (region, DB name, CI/CD, `model_mode`) |
| `infra/app-secrets.json` | ECS secret values (gitignored); Terraform uploads to Secrets Manager |
| Root `.env` | Local app/worker only (gitignored) |

Copy `terraform.tfvars.example` → `terraform.tfvars` if needed.

## AWS apply

```powershell
$env:AWS_PROFILE = "freight-hero"
$env:TF_VAR_db_password = "<strong-password>"
cd infra
terraform init
terraform apply
```

## Outputs

- `sqs_queue_url` — set as `SQS_QUEUE_URL` in ECS / `.env`
- `rds_endpoint` — build `DATABASE_URL` for LangGraph checkpoints
- `alb_dns_name` — public API URL
- `ecr_repository_url` — container registry (CI/CD pushes here)
- `codepipeline_name`, `codebuild_project_name`, `pipeline_artifacts_bucket` — when `enable_cicd = true`

## ECS runtime

- **API** and **worker** share `MODEL_MODE` from `var.model_mode` (default `live`).
- **Worker** also gets LangSmith env vars; API uses core env + secrets only.
- After CI/CD is enabled, ECS services ignore Terraform changes to `task_definition` so CodePipeline owns image rollouts.

## CI/CD

See [docs/DEPLOYMENT.md](../docs/DEPLOYMENT.md#cicd-github--codepipeline--codebuild--ecr--ecs). Requires an authorized CodeStar GitHub connection ARN in `terraform.tfvars`.

## Secrets (AWS Secrets Manager)

Copy `app-secrets.json.example` → `app-secrets.json` (gitignored), fill:

- `DATABASE_URL`
- `SQS_QUEUE_URL`
- `OPENROUTER_API_KEY` (required when `model_mode = live`)
- `LANGSMITH_API_KEY` (optional; injected into the worker as both `LANGSMITH_API_KEY` and `LANGCHAIN_API_KEY`)
- `API_KEY` (write API authentication)

Then `terraform apply` uploads to Secrets Manager.
