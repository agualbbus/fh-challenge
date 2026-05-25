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

variable "model_mode" {
  description = "MODEL_MODE env for ECS containers (mock | live). Worker and API use this value in AWS."
  type        = string
  default     = "live"
}

variable "enable_cicd" {
  description = "When true (and enable_aws_resources), provision CodePipeline + CodeBuild for GitHub → ECR → ECS."
  type        = bool
  default     = false
}

variable "github_owner" {
  description = "GitHub org or user for CodeStar source connection."
  type        = string
  default     = ""
}

variable "github_repo" {
  description = "GitHub repository name for CodeStar source connection."
  type        = string
  default     = ""
}

variable "github_branch" {
  description = "Branch that triggers the deploy pipeline."
  type        = string
  default     = "main"
}

variable "codestar_connection_arn" {
  description = "ARN of an authorized CodeStar Connections GitHub connection."
  type        = string
  default     = ""
}

variable "db_password" {
  description = "PostgreSQL master password (override via TF_VAR_db_password)."
  type        = string
  sensitive   = true
  default     = "change-me-in-tfvars"
}
