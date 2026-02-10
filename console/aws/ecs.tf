# --- ECS Cluster ---

resource "aws_ecs_cluster" "main" {
  name = "${var.project_name}-cluster"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

# --- IAM Roles ---

data "aws_iam_policy_document" "ecs_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "ecs_execution" {
  name               = "${var.project_name}-ecs-execution"
  assume_role_policy = data.aws_iam_policy_document.ecs_assume.json
}

resource "aws_iam_role_policy_attachment" "ecs_execution" {
  role       = aws_iam_role.ecs_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# Allow ECS to read secrets
resource "aws_iam_role_policy" "ecs_secrets" {
  name = "${var.project_name}-secrets-access"
  role = aws_iam_role.ecs_execution.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "secretsmanager:GetSecretValue"
      ]
      Resource = [
        aws_secretsmanager_secret.app_secrets.arn,
        aws_secretsmanager_secret.db_password.arn,
      ]
    }]
  })
}

resource "aws_iam_role" "ecs_task" {
  name               = "${var.project_name}-ecs-task"
  assume_role_policy = data.aws_iam_policy_document.ecs_assume.json
}

# --- CloudWatch Log Groups ---

resource "aws_cloudwatch_log_group" "forge_backend" {
  name              = "/ecs/${var.project_name}/backend"
  retention_in_days = 14
}

resource "aws_cloudwatch_log_group" "ecom_agents" {
  name              = "/ecs/${var.project_name}/ecom-agents"
  retention_in_days = 14
}

# --- Service Discovery (so forge-backend can reach ecom-agents by name) ---

resource "aws_service_discovery_private_dns_namespace" "main" {
  name = "${var.project_name}.local"
  vpc  = aws_vpc.main.id
}

resource "aws_service_discovery_service" "ecom_agents" {
  name = "ecom-agents"

  dns_config {
    namespace_id = aws_service_discovery_private_dns_namespace.main.id
    dns_records {
      ttl  = 10
      type = "A"
    }
    routing_policy = "MULTIVALUE"
  }

  health_check_custom_config {
    failure_threshold = 1
  }
}

# --- ECS Task Definition: ecom-agents ---

resource "aws_ecs_task_definition" "ecom_agents" {
  family                   = "${var.project_name}-ecom-agents"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.ecom_agents_cpu
  memory                   = var.ecom_agents_memory
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([{
    name  = "ecom-agents"
    image = var.ecom_agents_image != "" ? var.ecom_agents_image : "${aws_ecr_repository.ecom_agents.repository_url}:latest"

    portMappings = [{
      containerPort = 8050
      protocol      = "tcp"
    }]

    environment = [
      { name = "HOST", value = "0.0.0.0" },
      { name = "PORT", value = "8050" },
      { name = "LANGSMITH_PROJECT", value = "ecom-agents" },
      { name = "LANGSMITH_TRACING_V2", value = "true" },
      { name = "POSTGRES_HOST", value = aws_db_instance.postgres.address },
      { name = "POSTGRES_PORT", value = "5432" },
      { name = "POSTGRES_DB", value = "ecom_agents" },
      { name = "POSTGRES_USER", value = "ecom_admin" },
      { name = "REDIS_HOST", value = aws_elasticache_cluster.redis.cache_nodes[0].address },
      { name = "REDIS_PORT", value = "6379" },
      { name = "OLLAMA_BASE_URL", value = "http://localhost:11434" },
    ]

    secrets = [
      { name = "LANGSMITH_API_KEY", valueFrom = "${aws_secretsmanager_secret.app_secrets.arn}:LANGSMITH_API_KEY::" },
      { name = "OPENAI_API_KEY", valueFrom = "${aws_secretsmanager_secret.app_secrets.arn}:OPENAI_API_KEY::" },
      { name = "ANTHROPIC_API_KEY", valueFrom = "${aws_secretsmanager_secret.app_secrets.arn}:ANTHROPIC_API_KEY::" },
      { name = "SHOPIFY_ACCESS_TOKEN", valueFrom = "${aws_secretsmanager_secret.app_secrets.arn}:SHOPIFY_ACCESS_TOKEN::" },
      { name = "STRIPE_SECRET_KEY", valueFrom = "${aws_secretsmanager_secret.app_secrets.arn}:STRIPE_SECRET_KEY::" },
      { name = "PRINTFUL_API_KEY", valueFrom = "${aws_secretsmanager_secret.app_secrets.arn}:PRINTFUL_API_KEY::" },
      { name = "POSTGRES_PASSWORD", valueFrom = aws_secretsmanager_secret.db_password.arn },
    ]

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.ecom_agents.name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "ecs"
      }
    }

    healthCheck = {
      command     = ["CMD-SHELL", "python -c \"import urllib.request; urllib.request.urlopen('http://localhost:8050/health')\" || exit 1"]
      interval    = 30
      timeout     = 10
      retries     = 3
      startPeriod = 60
    }
  }])
}

# --- ECS Task Definition: forge-console backend ---

resource "aws_ecs_task_definition" "forge_backend" {
  family                   = "${var.project_name}-backend"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.backend_cpu
  memory                   = var.backend_memory
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([{
    name  = "forge-backend"
    image = var.forge_backend_image != "" ? var.forge_backend_image : "${aws_ecr_repository.forge_backend.repository_url}:latest"

    portMappings = [{
      containerPort = 8060
      protocol      = "tcp"
    }]

    environment = [
      { name = "FORGE_ECOM_AGENTS_URL", value = "http://ecom-agents.${var.project_name}.local:8050" },
      { name = "FORGE_LANGSMITH_PROJECT", value = "ecom-agents" },
      { name = "FORGE_CORS_ORIGINS", value = "[\"*\"]" },
    ]

    secrets = [
      { name = "FORGE_LANGSMITH_API_KEY", valueFrom = "${aws_secretsmanager_secret.app_secrets.arn}:LANGSMITH_API_KEY::" },
    ]

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.forge_backend.name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "ecs"
      }
    }

    healthCheck = {
      command     = ["CMD-SHELL", "python -c \"import urllib.request; urllib.request.urlopen('http://localhost:8060/api/health')\" || exit 1"]
      interval    = 30
      timeout     = 10
      retries     = 3
      startPeriod = 30
    }
  }])
}

# --- ECS Services ---

resource "aws_ecs_service" "ecom_agents" {
  name            = "ecom-agents"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.ecom_agents.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.ecs.id]
    assign_public_ip = false
  }

  service_registries {
    registry_arn = aws_service_discovery_service.ecom_agents.arn
  }
}

resource "aws_ecs_service" "forge_backend" {
  name            = "forge-backend"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.forge_backend.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.ecs.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.forge_backend.arn
    container_name   = "forge-backend"
    container_port   = 8060
  }

  depends_on = [aws_lb_listener_rule.api]
}
