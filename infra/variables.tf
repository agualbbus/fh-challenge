variable "project_name" {
  description = "Short name used for AWS resource naming."
  type        = string
  default     = "freight-watchtower"
}

variable "aws_region" {
  description = "AWS region for ECS/ECR/ALB (matches Temporal namespace region)."
  type        = string
  default     = "us-east-1"
}

variable "temporal_namespace_name" {
  description = "Temporal Cloud namespace name (2-64 chars, lowercase, hyphens)."
  type        = string
  default     = "freight-watchtower-dev"
}

variable "temporal_account_id" {
  description = "Optional Temporal Cloud account ID pin (TEMPORAL_CLOUD_ALLOWED_ACCOUNT_ID)."
  type        = string
  default     = ""
}

variable "temporal_retention_days" {
  description = "Workflow history retention in Temporal Cloud."
  type        = number
  default     = 14
}

variable "enable_aws_resources" {
  description = "When false, AWS skeleton resources are not created (Temporal-only apply)."
  type        = bool
  default     = true
}

variable "app_secrets_file" {
  description = "Gitignored JSON file of ECS secret key/values (copy from app-secrets.json.example)."
  type        = string
  default     = "app-secrets.json"
}
