output "ecr_repository_url" {
  description = "ECR URL for the application image (after AWS apply)."
  value       = var.enable_aws_resources ? aws_ecr_repository.app[0].repository_url : null
}

output "alb_dns_name" {
  description = "Public API load balancer DNS (after AWS apply)."
  value       = var.enable_aws_resources ? aws_lb.api[0].dns_name : null
}

output "sqs_queue_url" {
  description = "FIFO work queue URL for API publish / worker consume."
  value       = var.enable_aws_resources ? aws_sqs_queue.work[0].url : null
}

output "rds_endpoint" {
  description = "PostgreSQL endpoint for LangGraph checkpoints."
  value       = var.enable_aws_resources ? aws_db_instance.watchtower[0].endpoint : null
}

output "database_url_hint" {
  description = "Construct DATABASE_URL from RDS endpoint + db credentials in Secrets Manager."
  value       = var.enable_aws_resources ? "postgresql://${var.db_username}:<password>@${aws_db_instance.watchtower[0].address}:${aws_db_instance.watchtower[0].port}/${var.db_name}" : null
  sensitive   = true
}
