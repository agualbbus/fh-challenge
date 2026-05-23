resource "aws_ecr_repository" "app" {
  count = var.enable_aws_resources ? 1 : 0

  name                 = var.project_name
  image_tag_mutability = "MUTABLE"
  force_delete         = true

  image_scanning_configuration {
    scan_on_push = true
  }
}
