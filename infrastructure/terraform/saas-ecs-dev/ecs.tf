data "aws_cloudformation_stack" "sqs" {
  name = var.sqs_stack_name
}

locals {
  # CloudFormation outputs are a map[string]string in this data source.
  sqs_outputs = data.aws_cloudformation_stack.sqs.outputs

  ingest_queue_url              = lookup(local.sqs_outputs, "IngestQueueURL", "")
  ingest_dlq_url                = lookup(local.sqs_outputs, "IngestDLQURL", "")
  events_fast_lane_queue_url    = lookup(local.sqs_outputs, "EventsFastLaneQueueURL", "")
  events_fast_lane_dlq_url      = lookup(local.sqs_outputs, "EventsFastLaneDLQURL", "")
  inventory_reconcile_queue_url = lookup(local.sqs_outputs, "InventoryReconcileQueueURL", "")
  inventory_reconcile_dlq_url   = lookup(local.sqs_outputs, "InventoryReconcileDLQURL", "")
  export_report_queue_url       = lookup(local.sqs_outputs, "ExportReportQueueURL", "")
  export_report_dlq_url         = lookup(local.sqs_outputs, "ExportReportDLQURL", "")
  contract_quarantine_queue_url = lookup(local.sqs_outputs, "ContractQuarantineQueueURL", "")

  api_send_policy_arn       = lookup(local.sqs_outputs, "ApiSendPolicyArn", "")
  worker_consume_policy_arn = lookup(local.sqs_outputs, "WorkerConsumePolicyArn", "")

  api_base_url = local.has_cert ? "https://${var.api_domain}" : "http://${aws_lb.api.dns_name}"
}

resource "aws_ecs_cluster" "main" {
  name = "${local.name_prefix}-cluster"
  tags = merge(local.tags, { Name = "${local.name_prefix}-cluster" })
}

resource "aws_cloudwatch_log_group" "api" {
  name              = "/ecs/${local.name_prefix}/api"
  retention_in_days = 14
  tags              = local.tags
}

resource "aws_cloudwatch_log_group" "worker" {
  name              = "/ecs/${local.name_prefix}/worker"
  retention_in_days = 14
  tags              = local.tags
}

resource "aws_iam_role" "task_execution" {
  name = "${local.name_prefix}-ecs-exec"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect    = "Allow"
        Principal = { Service = "ecs-tasks.amazonaws.com" }
        Action    = "sts:AssumeRole"
      }
    ]
  })
  tags = local.tags
}

resource "aws_iam_role_policy_attachment" "task_execution" {
  role       = aws_iam_role.task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role" "api_task" {
  name = "${local.name_prefix}-api-task"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect    = "Allow"
        Principal = { Service = "ecs-tasks.amazonaws.com" }
        Action    = "sts:AssumeRole"
      }
    ]
  })
  tags = local.tags
}

resource "aws_iam_role" "worker_task" {
  name = "${local.name_prefix}-worker-task"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect    = "Allow"
        Principal = { Service = "ecs-tasks.amazonaws.com" }
        Action    = "sts:AssumeRole"
      }
    ]
  })
  tags = local.tags
}

resource "aws_iam_policy" "assume_tenant_roles" {
  name        = "${local.name_prefix}-assume-tenant-roles"
  description = "Allow assuming tenant Read/Write roles created by the public CloudFormation templates."
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = ["sts:AssumeRole"]
        Resource = [
          "arn:aws:iam::*:role/SecurityAutopilotReadRole",
          "arn:aws:iam::*:role/SecurityAutopilotWriteRole"
        ]
      }
    ]
  })
  tags = local.tags
}

resource "aws_iam_role_policy_attachment" "api_assume_roles" {
  role       = aws_iam_role.api_task.name
  policy_arn = aws_iam_policy.assume_tenant_roles.arn
}

resource "aws_iam_role_policy_attachment" "worker_assume_roles" {
  role       = aws_iam_role.worker_task.name
  policy_arn = aws_iam_policy.assume_tenant_roles.arn
}

resource "aws_iam_role_policy_attachment" "api_sqs_send" {
  count      = local.api_send_policy_arn != "" ? 1 : 0
  role       = aws_iam_role.api_task.name
  policy_arn = local.api_send_policy_arn
}

resource "aws_iam_role_policy_attachment" "worker_sqs_consume" {
  count      = local.worker_consume_policy_arn != "" ? 1 : 0
  role       = aws_iam_role.worker_task.name
  policy_arn = local.worker_consume_policy_arn
}

resource "aws_security_group" "api_task" {
  name        = "${local.name_prefix}-api-task-sg"
  description = "Allow ALB -> API task traffic"
  vpc_id      = aws_vpc.main.id

  ingress {
    from_port       = 8000
    to_port         = 8000
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(local.tags, { Name = "${local.name_prefix}-api-task-sg" })
}

resource "aws_security_group" "worker_task" {
  name        = "${local.name_prefix}-worker-task-sg"
  description = "No inbound; outbound only"
  vpc_id      = aws_vpc.main.id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(local.tags, { Name = "${local.name_prefix}-worker-task-sg" })
}

locals {
  base_env = [
    { name = "APP_NAME", value = var.app_name },
    { name = "ENV", value = var.app_env },
    { name = "LOG_LEVEL", value = var.log_level },

    { name = "AWS_REGION", value = var.aws_region },
    { name = "SAAS_AWS_ACCOUNT_ID", value = data.aws_caller_identity.current.account_id },
    { name = "ROLE_SESSION_NAME", value = "security-autopilot-session" },

    # Queues from the deployed CloudFormation stack.
    { name = "SQS_INGEST_QUEUE_URL", value = local.ingest_queue_url },
    { name = "SQS_INGEST_DLQ_URL", value = local.ingest_dlq_url },
    { name = "SQS_EVENTS_FAST_LANE_QUEUE_URL", value = local.events_fast_lane_queue_url },
    { name = "SQS_EVENTS_FAST_LANE_DLQ_URL", value = local.events_fast_lane_dlq_url },
    { name = "SQS_INVENTORY_RECONCILE_QUEUE_URL", value = local.inventory_reconcile_queue_url },
    { name = "SQS_INVENTORY_RECONCILE_DLQ_URL", value = local.inventory_reconcile_dlq_url },
    { name = "SQS_EXPORT_REPORT_QUEUE_URL", value = local.export_report_queue_url },
    { name = "SQS_EXPORT_REPORT_DLQ_URL", value = local.export_report_dlq_url },
    { name = "SQS_CONTRACT_QUARANTINE_QUEUE_URL", value = local.contract_quarantine_queue_url },

    { name = "WORKER_POOL", value = var.worker_pool },

    { name = "API_PUBLIC_URL", value = local.api_base_url },
    { name = "FRONTEND_URL", value = var.frontend_url },
    { name = "CORS_ORIGINS", value = var.cors_origins },
  ]
}

resource "aws_ecs_task_definition" "api" {
  family                   = "${local.name_prefix}-api"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.api_cpu
  memory                   = var.api_memory
  execution_role_arn       = aws_iam_role.task_execution.arn
  task_role_arn            = aws_iam_role.api_task.arn

  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = var.cpu_architecture
  }

  container_definitions = jsonencode([
    {
      name      = "api"
      image     = "${aws_ecr_repository.app.repository_url}:${var.image_tag}"
      essential = true
      portMappings = [
        { containerPort = 8000, hostPort = 8000, protocol = "tcp" }
      ]
      environment = concat(local.base_env, [
        { name = "DATABASE_URL", value = var.database_url },
        { name = "DATABASE_URL_SYNC", value = var.database_url_sync },
        { name = "JWT_SECRET", value = var.jwt_secret },
        { name = "CONTROL_PLANE_EVENTS_SECRET", value = var.control_plane_events_secret },
        { name = "CONTROL_PLANE_SHADOW_MODE", value = var.control_plane_shadow_mode ? "true" : "false" },
      ])
      command = [
        "/bin/sh",
        "-lc",
        "alembic upgrade head && uvicorn backend.main:app --host 0.0.0.0 --port 8000"
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.api.name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "api"
        }
      }
    }
  ])

  tags = local.tags
}

resource "aws_ecs_task_definition" "worker" {
  family                   = "${local.name_prefix}-worker"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.worker_cpu
  memory                   = var.worker_memory
  execution_role_arn       = aws_iam_role.task_execution.arn
  task_role_arn            = aws_iam_role.worker_task.arn

  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = var.cpu_architecture
  }

  container_definitions = jsonencode([
    {
      name      = "worker"
      image     = "${aws_ecr_repository.app.repository_url}:${var.image_tag}"
      essential = true
      environment = concat(local.base_env, [
        { name = "DATABASE_URL", value = var.database_url },
        { name = "DATABASE_URL_SYNC", value = var.database_url_sync },
        { name = "JWT_SECRET", value = var.jwt_secret },
        { name = "CONTROL_PLANE_EVENTS_SECRET", value = var.control_plane_events_secret },
        { name = "CONTROL_PLANE_SHADOW_MODE", value = var.control_plane_shadow_mode ? "true" : "false" },
      ])
      command = [
        "/bin/sh",
        "-lc",
        "python -m backend.workers.main"
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.worker.name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "worker"
        }
      }
    }
  ])

  tags = local.tags
}

resource "aws_ecs_service" "api" {
  name            = "${local.name_prefix}-api"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.api.arn
  desired_count   = var.api_desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = [aws_subnet.public_a.id, aws_subnet.public_b.id]
    security_groups  = [aws_security_group.api_task.id]
    assign_public_ip = true
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.api.arn
    container_name   = "api"
    container_port   = 8000
  }

  depends_on = [
    aws_lb_listener.http_forward,
    aws_lb_listener.http_redirect,
    aws_lb_listener.https
  ]

  tags = local.tags
}

resource "aws_ecs_service" "worker" {
  name            = "${local.name_prefix}-worker"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.worker.arn
  desired_count   = var.worker_desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = [aws_subnet.public_a.id, aws_subnet.public_b.id]
    security_groups  = [aws_security_group.worker_task.id]
    assign_public_ip = true
  }

  tags = local.tags
}

