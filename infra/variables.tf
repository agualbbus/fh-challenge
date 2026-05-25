variable "project_name" {
  description = "Short name used for AWS resource naming."
  type        = string
  default     = "freight-watchtower"
}

variable "aws_region" {
  description = "AWS region for ECS/ECR/ALB/RDS/SQS."
  type        = string
  default     = "us-east-1"
}

variable "enable_aws_resources" {
  description = "When false, AWS resources are not created (plan-only / local dev)."
  type        = bool
  default     = true
}

variable "app_secrets_file" {
  description = "Gitignored JSON file of ECS secret key/values (copy from app-secrets.json.example)."
  type        = string
  default     = "app-secrets.json"
}

variable "db_instance_class" {
  description = "RDS instance class for PostgreSQL."
  type        = string
  default     = "db.t4g.micro"
}

variable "db_name" {
  description = "PostgreSQL database name."
  type        = string
  default     = "watchtower"
}

variable "db_username" {
  description = "PostgreSQL master username."
  type        = string
  default     = "watchtower"
}

variable "image_tag" {
  description = "Container image tag pushed to ECR."
  type        = string
  default     = "latest"
}

variable "db_password" {
  description = "PostgreSQL master password (override via TF_VAR_db_password)."
  type        = string
  sensitive   = true
  default     = "change-me-in-tfvars"
}
