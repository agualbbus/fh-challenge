data "aws_region" "current" {}

resource "aws_cloudwatch_log_group" "api" {
  count             = var.enable_aws_resources ? 1 : 0
  name              = "/ecs/${var.project_name}-api"
  retention_in_days = 14
}

resource "aws_cloudwatch_log_group" "worker" {
  count             = var.enable_aws_resources ? 1 : 0
  name              = "/ecs/${var.project_name}-worker"
  retention_in_days = 14
}

data "aws_iam_policy_document" "ecs_tasks_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "ecs_execution" {
  count              = var.enable_aws_resources ? 1 : 0
  name               = "${var.project_name}-ecs-execution"
  assume_role_policy = data.aws_iam_policy_document.ecs_tasks_assume.json
}

resource "aws_iam_role_policy_attachment" "ecs_execution_managed" {
  count      = var.enable_aws_resources ? 1 : 0
  role       = aws_iam_role.ecs_execution[0].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

data "aws_iam_policy_document" "execution_secrets" {
  count = var.enable_aws_resources ? 1 : 0
  statement {
    actions   = ["secretsmanager:GetSecretValue"]
    resources = [aws_secretsmanager_secret.app[0].arn]
  }
}

resource "aws_iam_role_policy" "execution_secrets" {
  count  = var.enable_aws_resources ? 1 : 0
  name   = "${var.project_name}-execution-secrets"
  role   = aws_iam_role.ecs_execution[0].id
  policy = data.aws_iam_policy_document.execution_secrets[0].json
}

resource "aws_iam_role" "ecs_task" {
  count              = var.enable_aws_resources ? 1 : 0
  name               = "${var.project_name}-ecs-task"
  assume_role_policy = data.aws_iam_policy_document.ecs_tasks_assume.json
}

data "aws_iam_policy_document" "task_runtime" {
  count = var.enable_aws_resources ? 1 : 0
  statement {
    actions = [
      "sqs:SendMessage",
      "sqs:ReceiveMessage",
      "sqs:DeleteMessage",
      "sqs:GetQueueAttributes",
      "sqs:GetQueueUrl",
      "sqs:ChangeMessageVisibility",
    ]
    resources = [
      aws_sqs_queue.work[0].arn,
      aws_sqs_queue.dlq[0].arn,
    ]
  }
}

resource "aws_iam_role_policy" "task_runtime" {
  count  = var.enable_aws_resources ? 1 : 0
  name   = "${var.project_name}-task-runtime"
  role   = aws_iam_role.ecs_task[0].id
  policy = data.aws_iam_policy_document.task_runtime[0].json
}

locals {
  image_tag = var.enable_aws_resources ? "${aws_ecr_repository.app[0].repository_url}:${var.image_tag}" : ""
  secret_arn = var.enable_aws_resources ? aws_secretsmanager_secret.app[0].arn : ""

  common_secrets = var.enable_aws_resources ? [
    { name = "DATABASE_URL", valueFrom = "${local.secret_arn}:DATABASE_URL::" },
    { name = "SQS_QUEUE_URL", valueFrom = "${local.secret_arn}:SQS_QUEUE_URL::" },
    { name = "OPENROUTER_API_KEY", valueFrom = "${local.secret_arn}:OPENROUTER_API_KEY::" },
    { name = "API_KEY", valueFrom = "${local.secret_arn}:API_KEY::" },
  ] : []

  common_env = [
    { name = "AWS_REGION", value = var.aws_region },
    { name = "MODEL_MODE", value = var.model_mode },
  ]

  worker_env = concat(local.common_env, [
    { name = "LANGSMITH_TRACING", value = "true" },
    { name = "LANGSMITH_PROJECT", value = "fh-prod" },
    { name = "LANGSMITH_ENDPOINT", value = "https://api.smith.langchain.com" },
    # Keep legacy LangChain env names populated for SDK compatibility.
    { name = "LANGCHAIN_TRACING_V2", value = "true" },
    { name = "LANGCHAIN_PROJECT", value = "fh-prod" },
  ])

  worker_secrets = concat(local.common_secrets, [
    { name = "LANGSMITH_API_KEY", valueFrom = "${local.secret_arn}:LANGSMITH_API_KEY::" },
    { name = "LANGCHAIN_API_KEY", valueFrom = "${local.secret_arn}:LANGSMITH_API_KEY::" },
  ])
}

resource "aws_ecs_task_definition" "api" {
  count                    = var.enable_aws_resources ? 1 : 0
  family                   = "${var.project_name}-api"
  cpu                      = "512"
  memory                   = "1024"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  execution_role_arn       = aws_iam_role.ecs_execution[0].arn
  task_role_arn            = aws_iam_role.ecs_task[0].arn

  container_definitions = jsonencode([
    {
      name      = "api"
      image     = local.image_tag
      essential = true
      command   = ["uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
      portMappings = [
        { containerPort = 8000, protocol = "tcp" }
      ]
      environment = local.worker_env
      secrets     = local.worker_secrets
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.api[0].name
          awslogs-region        = data.aws_region.current.region
          awslogs-stream-prefix = "api"
        }
      }
    }
  ])
}

resource "aws_ecs_task_definition" "worker" {
  count                    = var.enable_aws_resources ? 1 : 0
  family                   = "${var.project_name}-worker"
  cpu                      = "512"
  memory                   = "1024"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  execution_role_arn       = aws_iam_role.ecs_execution[0].arn
  task_role_arn            = aws_iam_role.ecs_task[0].arn

  container_definitions = jsonencode([
    {
      name        = "worker"
      image       = local.image_tag
      essential   = true
      command     = ["python", "-m", "app.worker"]
      environment = local.common_env
      secrets     = local.common_secrets
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.worker[0].name
          awslogs-region        = data.aws_region.current.region
          awslogs-stream-prefix = "worker"
        }
      }
    }
  ])
}

resource "aws_ecs_service" "api" {
  count           = var.enable_aws_resources ? 1 : 0
  name            = "${var.project_name}-api"
  cluster         = aws_ecs_cluster.main[0].id
  task_definition = aws_ecs_task_definition.api[0].arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = aws_subnet.public[*].id
    security_groups  = [aws_security_group.ecs_tasks[0].id]
    assign_public_ip = true
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.api[0].arn
    container_name   = "api"
    container_port   = 8000
  }

  depends_on = [aws_lb_listener.api]
}

resource "aws_ecs_service" "worker" {
  count           = var.enable_aws_resources ? 1 : 0
  name            = "${var.project_name}-worker"
  cluster         = aws_ecs_cluster.main[0].id
  task_definition = aws_ecs_task_definition.worker[0].arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = aws_subnet.public[*].id
    security_groups  = [aws_security_group.ecs_tasks[0].id]
    assign_public_ip = true
  }
}
