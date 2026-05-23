# Infrastructure (Terraform)

## Prerequisites

- [Terraform](https://developer.hashicorp.com/terraform/install) >= 1.5 (or `terraform.exe` in this directory on Windows)
- [Temporal Cloud](https://cloud.temporal.io) account
- AWS account with credentials for Terraform (`AWS_PROFILE` or `AWS_*`)

## Config split (do not use `.env` for Terraform)

| Source | Purpose |
| --- | --- |
| Shell env `TEMPORAL_CLOUD_API_KEY` | Terraform `temporalcloud` provider (account-level key) |
| Shell env `AWS_PROFILE` or `AWS_*` | Terraform `aws` provider |
| `terraform.tfvars` | Non-secret inputs (region, namespace name) |
| `infra/app-secrets.json` | ECS secret values (gitignored); Terraform uploads to Secrets Manager |
| Root `.env` | Local app/worker only (gitignored) |

Copy `terraform.tfvars.example` → `terraform.tfvars` if needed.

## Temporal Cloud — apply namespace (Phase 1)

1. Create an **account-level** API key in Temporal Cloud (Account Settings → API Keys).
2. Export credentials (PowerShell):

   ```powershell
   $env:TEMPORAL_CLOUD_API_KEY = "<secret>"
   # Optional:
   $env:TEMPORAL_CLOUD_ALLOWED_ACCOUNT_ID = "<account-id>"
   ```

3. Initialize and apply:

   ```bash
   cd infra
   terraform init
   terraform apply -target=temporalcloud_namespace.fh
   ```

4. Note outputs: `temporal_grpc_address`, `temporal_namespace_id`.
5. Create a **namespace** API key in the UI (Namespaces → your namespace → API Keys).
6. Copy into gitignored root `.env` for app/worker:

   ```env
   TEMPORAL_ADDRESS=<temporal_grpc_address output>
   TEMPORAL_NAMESPACE=<temporal_namespace_id output>
   TEMPORAL_API_KEY=<namespace key secret>
   TEMPORAL_TASK_QUEUE=freight-watchtower
   ```

## AWS skeleton (VPC, ECS cluster, ALB, ECR, Secrets Manager)

```powershell
$env:AWS_PROFILE = "freight-hero"   # required if credentials are in a named profile
$env:AWS_REGION = "us-east-1"
$env:TEMPORAL_CLOUD_API_KEY = "<account-level key>"   # for Temporal provider refresh
cd infra
.\terraform.exe init    # Windows: use .\terraform.exe from this folder
.\terraform.exe apply
```

On Windows PowerShell, quote targeted applies: `-target="temporalcloud_namespace.fh"` (unquoted `.fh` is parsed incorrectly).

IAM: `PowerUserAccess` (or equivalent EC2/ECS/ELB/ECR/Secrets Manager permissions) for the Terraform user. Security group descriptions must be ASCII-only.

After apply, note outputs: `ecr_repository_url`, `alb_dns_name`, `temporal_grpc_address`.

ECS **task definitions and services** are not created yet — skeleton only until deploy phase.

## Secrets (AWS Secrets Manager)

**Recommended:** gitignored JSON file + Terraform (no console paste).

1. Copy the example file:

   ```bash
   cd infra
   cp app-secrets.json.example app-secrets.json   # PowerShell: Copy-Item app-secrets.json.example app-secrets.json
   ```

2. Edit `app-secrets.json` with real values (same keys as `.env.example` secrets — **not** `TEMPORAL_CLOUD_API_KEY`).

3. Apply (with `AWS_PROFILE` set):

   ```bash
   terraform apply
   ```

Terraform creates secret `freight-watchtower/app` and uploads the JSON via `aws_secretsmanager_secret_version`. Updating the file and re-running `apply` pushes a new secret version.

If `app-secrets.json` is missing, Terraform still creates the empty secret resource but **skips** the version (useful for plan-only; ECS deploy needs the file).

### Recreate from scratch

1. Delete the secret in AWS Console (or `aws secretsmanager delete-secret --secret-id freight-watchtower/app --force-delete-without-recovery`).
2. Ensure `app-secrets.json` exists and is filled.
3. `terraform apply` — recreates the secret and version.

To refresh values only: edit `app-secrets.json` and `terraform apply` (no console).

### When to use what

| Environment | Where secrets live |
| --- | --- |
| Local (`make dev-api`, `docker compose`) | Root `.env` (copy from `.env.example`) |
| AWS ECS (deploy phase) | `infra/app-secrets.json` → Secrets Manager (via Terraform) |

### Two Temporal keys (do not mix)

| Variable | Scope | Used by |
| --- | --- | --- |
| `TEMPORAL_CLOUD_API_KEY` | Temporal Cloud **account** | Terraform only (shell env) |
| `TEMPORAL_API_KEY` | **Namespace** | App + worker (`.env` locally; `app-secrets.json` on ECS) |

Create the namespace key: Temporal Cloud → Namespaces → `freight-watchtower-dev` → API Keys.

### `app-secrets.json` shape

See [app-secrets.json.example](app-secrets.json.example). Omit optional keys or use `""` if unused.

Non-secret Temporal config belongs in ECS task environment variables (from `terraform output`), not in this file:

- `TEMPORAL_ADDRESS` — `temporal_grpc_address` output
- `TEMPORAL_NAMESPACE` — `temporal_namespace_name` or `temporal_namespace_id` output
- `TEMPORAL_TASK_QUEUE` — `freight-watchtower`

### Console / CLI (optional fallback)

Manual `put-secret-value` is only needed if you are not using `app-secrets.json`. Prefer Terraform to avoid drift.

Local development does **not** require Secrets Manager — use `.env` only.

**State file:** Secret values are stored in Terraform state (`terraform.tfstate`). Keep state local/gitignored (default here) or use an encrypted remote backend for teams. Never commit `*.tfstate` with real secrets.
