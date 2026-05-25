resource "aws_iam_openid_connect_provider" "github" {
  count = var.enable_aws_resources ? 1 : 0

  url             = "https://token.actions.githubusercontent.com"
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = ["6938fd4d98bab03faadb97b34396831e3780aea1"]
}

data "aws_iam_policy_document" "github_deploy_assume" {
  count = var.enable_aws_resources ? 1 : 0

  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]
    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github[0].arn]
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"
      values = [
        for branch in var.github_deploy_branches :
        "repo:agualbbus/fh-challenge:ref:refs/heads/${branch}"
      ]
    }
  }
}

resource "aws_iam_role" "github_deploy" {
  count = var.enable_aws_resources ? 1 : 0

  name               = "${var.project_name}-github-deploy"
  assume_role_policy = data.aws_iam_policy_document.github_deploy_assume[0].json
}

data "aws_iam_policy_document" "github_deploy" {
  count = var.enable_aws_resources ? 1 : 0

  statement {
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }

  statement {
    actions = [
      "ecr:BatchCheckLayerAvailability",
      "ecr:BatchGetImage",
      "ecr:CompleteLayerUpload",
      "ecr:InitiateLayerUpload",
      "ecr:PutImage",
      "ecr:UploadLayerPart",
    ]
    resources = [aws_ecr_repository.app[0].arn]
  }

  statement {
    actions = [
      "ecs:UpdateService",
      "ecs:DescribeServices",
    ]
    resources = [
      aws_ecs_service.api[0].arn,
      aws_ecs_service.worker[0].arn,
    ]
  }
}

resource "aws_iam_role_policy" "github_deploy" {
  count = var.enable_aws_resources ? 1 : 0

  name   = "${var.project_name}-github-deploy"
  role   = aws_iam_role.github_deploy[0].id
  policy = data.aws_iam_policy_document.github_deploy[0].json
}
