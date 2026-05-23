resource "temporalcloud_namespace" "fh" {
  name             = var.temporal_namespace_name
  regions          = ["aws-us-east-1"]
  retention_days   = var.temporal_retention_days
  api_key_auth     = true
  namespace_lifecycle = {
    enable_delete_protection = false
  }
}
