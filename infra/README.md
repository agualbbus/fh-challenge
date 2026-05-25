# Infrastructure (Terraform)

## Prerequisites

- [Terraform](https://developer.hashicorp.com/terraform/install) >= 1.5
- AWS account with credentials (`AWS_PROFILE` or `AWS_*`)

## Config split

| Source | Purpose |
| --- | --- |
| Shell env `AWS_PROFILE` or `AWS_*` | Terraform `aws` provider |
| `terraform.tfvars` | Non-secret inputs (region, DB name) |
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
- `alb_dns_name` — public API URL (after ECS services are wired)
- `ecr_repository_url` — push container image
- `github_deploy_role_arn` — set as GitHub repo secret `AWS_DEPLOY_ROLE_ARN` for CI deploys

## CI/CD

Terraform provisions a GitHub OIDC provider and deploy IAM role (`freight-watchtower-github-deploy`). Trusted branches default to `github-ecs-setup` (test) and `main` (`var.github_deploy_branches`). GitHub Actions assumes the role via OIDC — test branch pushes only publish `:sha`; `main` (or manual `deploy_ecs=true`) also rolls ECS. No CodePipeline or long-lived AWS keys in GitHub.

## Secrets (AWS Secrets Manager)

Copy `app-secrets.json.example` → `app-secrets.json` (gitignored), fill:

- `DATABASE_URL`
- `SQS_QUEUE_URL`
- `API_KEY`
- `OPENROUTER_API_KEY` (optional for mock mode)
- `LANGSMITH_API_KEY` (optional; injected into the worker as both `LANGSMITH_API_KEY` and `LANGCHAIN_API_KEY`)

Then `terraform apply` uploads to Secrets Manager.
