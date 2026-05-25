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

## Secrets (AWS Secrets Manager)

Copy `app-secrets.json.example` → `app-secrets.json` (gitignored), fill:

- `DATABASE_URL`
- `SQS_QUEUE_URL`
- `OPENROUTER_API_KEY`
- `LANGSMITH_API_KEY` (optional; injected into the worker as both `LANGSMITH_API_KEY` and `LANGCHAIN_API_KEY`)

Then `terraform apply` uploads to Secrets Manager.