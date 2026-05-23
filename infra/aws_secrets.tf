resource "aws_secretsmanager_secret" "app" {
  count = var.enable_aws_resources ? 1 : 0

  name        = "${var.project_name}/app"
  description = "Application secrets (Temporal namespace key, LLM keys) - populated from app-secrets.json"

  recovery_window_in_days = 0
}

locals {
  app_secrets_path = "${path.module}/${var.app_secrets_file}"
  app_secrets_set  = var.enable_aws_resources && fileexists(local.app_secrets_path)
  app_secrets_json = local.app_secrets_set ? jsondecode(file(local.app_secrets_path)) : {}
}

resource "aws_secretsmanager_secret_version" "app" {
  count = local.app_secrets_set ? 1 : 0

  secret_id     = aws_secretsmanager_secret.app[0].id
  secret_string = jsonencode(local.app_secrets_json)
}

# Copy app-secrets.json.example -> app-secrets.json (gitignored), fill values, then terraform apply.
# See infra/README.md#secrets-aws-secrets-manager
