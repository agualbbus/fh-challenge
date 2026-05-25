data "aws_caller_identity" "current" {
  count = local.cicd_enabled ? 1 : 0
}

locals {
  cicd_enabled = var.enable_aws_resources && var.enable_cicd
}

resource "aws_s3_bucket" "pipeline_artifacts" {
  count  = local.cicd_enabled ? 1 : 0
  bucket = "${var.project_name}-pipeline-artifacts"

  tags = {
    Name = "${var.project_name}-pipeline-artifacts"
  }
}

resource "aws_s3_bucket_public_access_block" "pipeline_artifacts" {
  count  = local.cicd_enabled ? 1 : 0
  bucket = aws_s3_bucket.pipeline_artifacts[0].id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "pipeline_artifacts" {
  count  = local.cicd_enabled ? 1 : 0
  bucket = aws_s3_bucket.pipeline_artifacts[0].id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_versioning" "pipeline_artifacts" {
  count  = local.cicd_enabled ? 1 : 0
  bucket = aws_s3_bucket.pipeline_artifacts[0].id

  versioning_configuration {
    status = "Enabled"
  }
}

data "aws_iam_policy_document" "codebuild_assume" {
  count = local.cicd_enabled ? 1 : 0

  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["codebuild.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "codebuild" {
  count              = local.cicd_enabled ? 1 : 0
  name               = "${var.project_name}-codebuild"
  assume_role_policy = data.aws_iam_policy_document.codebuild_assume[0].json
}

data "aws_iam_policy_document" "codebuild" {
  count = local.cicd_enabled ? 1 : 0

  statement {
    actions = [
      "logs:CreateLogGroup",
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]
    resources = ["arn:aws:logs:${var.aws_region}:${data.aws_caller_identity.current[0].account_id}:log-group:/aws/codebuild/*"]
  }

  statement {
    actions = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }

  statement {
    actions = [
      "ecr:BatchCheckLayerAvailability",
      "ecr:GetDownloadUrlForLayer",
      "ecr:BatchGetImage",
      "ecr:PutImage",
      "ecr:InitiateLayerUpload",
      "ecr:UploadLayerPart",
      "ecr:CompleteLayerUpload",
    ]
    resources = [aws_ecr_repository.app[0].arn]
  }

  statement {
    actions = [
      "s3:GetObject",
      "s3:GetObjectVersion",
      "s3:PutObject",
    ]
    resources = [
      "${aws_s3_bucket.pipeline_artifacts[0].arn}/*",
    ]
  }

  statement {
    actions = [
      "s3:ListBucket",
    ]
    resources = [aws_s3_bucket.pipeline_artifacts[0].arn]
  }
}

resource "aws_iam_role_policy" "codebuild" {
  count  = local.cicd_enabled ? 1 : 0
  name   = "${var.project_name}-codebuild"
  role   = aws_iam_role.codebuild[0].id
  policy = data.aws_iam_policy_document.codebuild[0].json
}

resource "aws_codebuild_project" "app" {
  count        = local.cicd_enabled ? 1 : 0
  name         = "${var.project_name}-build"
  service_role = aws_iam_role.codebuild[0].arn

  artifacts {
    type = "CODEPIPELINE"
  }

  environment {
    compute_type                = "BUILD_GENERAL1_SMALL"
    image                       = "aws/codebuild/amazonlinux2-x86_64-standard:5.0"
    type                        = "LINUX_CONTAINER"
    privileged_mode             = true
    image_pull_credentials_type = "CODEBUILD"

    environment_variable {
      name  = "AWS_DEFAULT_REGION"
      value = var.aws_region
    }

    environment_variable {
      name  = "ECR_REPOSITORY_URL"
      value = aws_ecr_repository.app[0].repository_url
    }
  }

  source {
    type      = "CODEPIPELINE"
    buildspec = "buildspec.yml"
  }
}

data "aws_iam_policy_document" "codepipeline_assume" {
  count = local.cicd_enabled ? 1 : 0

  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["codepipeline.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "codepipeline" {
  count              = local.cicd_enabled ? 1 : 0
  name               = "${var.project_name}-codepipeline"
  assume_role_policy = data.aws_iam_policy_document.codepipeline_assume[0].json
}

data "aws_iam_policy_document" "codepipeline" {
  count = local.cicd_enabled ? 1 : 0

  statement {
    actions = [
      "s3:GetObject",
      "s3:GetObjectVersion",
      "s3:PutObject",
      "s3:GetBucketVersioning",
      "s3:GetBucketLocation",
    ]
    resources = [
      aws_s3_bucket.pipeline_artifacts[0].arn,
      "${aws_s3_bucket.pipeline_artifacts[0].arn}/*",
    ]
  }

  statement {
    actions = [
      "codestar-connections:UseConnection",
    ]
    resources = [var.codestar_connection_arn]
  }

  statement {
    actions = [
      "codebuild:BatchGetBuilds",
      "codebuild:StartBuild",
    ]
    resources = [aws_codebuild_project.app[0].arn]
  }

  statement {
    actions = [
      "ecs:DescribeServices",
      "ecs:DescribeTaskDefinition",
      "ecs:DescribeTasks",
      "ecs:ListTasks",
      "ecs:RegisterTaskDefinition",
      "ecs:UpdateService",
    ]
    resources = ["*"]
  }

  statement {
    actions = ["iam:PassRole"]
    resources = [
      aws_iam_role.ecs_execution[0].arn,
      aws_iam_role.ecs_task[0].arn,
    ]
  }
}

resource "aws_iam_role_policy" "codepipeline" {
  count  = local.cicd_enabled ? 1 : 0
  name   = "${var.project_name}-codepipeline"
  role   = aws_iam_role.codepipeline[0].id
  policy = data.aws_iam_policy_document.codepipeline[0].json
}

resource "aws_codepipeline" "app" {
  count    = local.cicd_enabled ? 1 : 0
  name     = "${var.project_name}-pipeline"
  role_arn = aws_iam_role.codepipeline[0].arn

  artifact_store {
    location = aws_s3_bucket.pipeline_artifacts[0].bucket
    type     = "S3"
  }

  stage {
    name = "Source"

    action {
      name             = "Source"
      category         = "Source"
      owner            = "AWS"
      provider         = "CodeStarSourceConnection"
      version          = "1"
      output_artifacts = ["source_output"]

      configuration = {
        ConnectionArn    = var.codestar_connection_arn
        FullRepositoryId = "${var.github_owner}/${var.github_repo}"
        BranchName       = var.github_branch
      }
    }
  }

  stage {
    name = "Build"

    action {
      name             = "Build"
      category         = "Build"
      owner            = "AWS"
      provider         = "CodeBuild"
      version          = "1"
      input_artifacts  = ["source_output"]
      output_artifacts = ["build_output"]

      configuration = {
        ProjectName = aws_codebuild_project.app[0].name
      }
    }
  }

  stage {
    name = "DeployAPI"

    action {
      name            = "DeployAPI"
      category        = "Deploy"
      owner           = "AWS"
      provider        = "ECS"
      version         = "1"
      input_artifacts = ["build_output"]

      configuration = {
        ClusterName = aws_ecs_cluster.main[0].name
        ServiceName = aws_ecs_service.api[0].name
        FileName    = "imagedefinitions-api.json"
      }
    }
  }

  stage {
    name = "DeployWorker"

    action {
      name            = "DeployWorker"
      category        = "Deploy"
      owner           = "AWS"
      provider        = "ECS"
      version         = "1"
      input_artifacts = ["build_output"]

      configuration = {
        ClusterName = aws_ecs_cluster.main[0].name
        ServiceName = aws_ecs_service.worker[0].name
        FileName    = "imagedefinitions-worker.json"
      }
    }
  }
}
