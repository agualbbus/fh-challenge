output "temporal_namespace_id" {
  description = "Temporal Cloud namespace ID (name.account_id)."
  value       = temporalcloud_namespace.fh.id
}

output "temporal_namespace_name" {
  description = "Temporal Cloud namespace name."
  value       = temporalcloud_namespace.fh.name
}

output "temporal_grpc_address" {
  description = "gRPC address for API key clients (use in .env TEMPORAL_ADDRESS)."
  value       = temporalcloud_namespace.fh.endpoints.grpc_address
}

output "temporal_web_address" {
  description = "Temporal Cloud Web UI URL for this namespace."
  value       = temporalcloud_namespace.fh.endpoints.web_address
}

output "ecr_repository_url" {
  description = "ECR URL for the application image (after AWS apply)."
  value       = var.enable_aws_resources ? aws_ecr_repository.app[0].repository_url : null
}

output "alb_dns_name" {
  description = "Public API load balancer DNS (after AWS apply)."
  value       = var.enable_aws_resources ? aws_lb.api[0].dns_name : null
}
