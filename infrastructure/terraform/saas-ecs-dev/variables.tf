variable "aws_region" {
  type        = string
  description = "AWS region to deploy into."
  default     = "eu-north-1"
}

variable "name_prefix" {
  type        = string
  description = "Prefix for resource names."
  default     = "security-autopilot-dev"
}

variable "tags" {
  type        = map(string)
  description = "Extra tags to apply."
  default     = {}
}

variable "vpc_cidr" {
  type        = string
  description = "CIDR for the dev VPC."
  default     = "10.42.0.0/16"
}

variable "ecr_repo_name" {
  type        = string
  description = "ECR repo name."
  default     = "security-autopilot-app"
}

variable "image_tag" {
  type        = string
  description = "Image tag to deploy from ECR."
  default     = "dev"
}

variable "certificate_arn" {
  type        = string
  description = "Optional ACM certificate ARN in this region. When set, enables HTTPS on the ALB."
  default     = ""
}

variable "api_domain" {
  type        = string
  description = "Public API hostname (used for API_PUBLIC_URL when HTTPS is enabled)."
  default     = "api.valensjewelry.com"
}

variable "app_name" {
  type        = string
  description = "APP_NAME env var."
  default     = "AWS Security Autopilot"
}

variable "app_env" {
  type        = string
  description = "ENV env var (local|dev|prod)."
  default     = "dev"
}

variable "log_level" {
  type        = string
  description = "LOG_LEVEL env var."
  default     = "INFO"
}

variable "frontend_url" {
  type        = string
  description = "Frontend URL used for redirects/invites."
  default     = "https://valensjewelry.com"
}

variable "cors_origins" {
  type        = string
  description = "Comma-separated CORS origins."
  default     = "https://valensjewelry.com"
}

variable "worker_pool" {
  type        = string
  description = "WORKER_POOL (legacy|events|inventory|export|all)."
  default     = "all"
}

variable "sqs_stack_name" {
  type        = string
  description = "Name of the CloudFormation SQS stack to pull queue URLs/policy ARNs from."
  default     = "security-autopilot-sqs-queues"
}

# Secrets / required config
variable "database_url" {
  type        = string
  description = "DATABASE_URL (Neon async URL)."
  sensitive   = true
}

variable "database_url_sync" {
  type        = string
  description = "Optional DATABASE_URL_SYNC (psycopg2 URL for Alembic/worker). If empty, code derives it."
  default     = ""
  sensitive   = true
}

variable "jwt_secret" {
  type        = string
  description = "JWT_SECRET for signing access tokens."
  sensitive   = true
}

variable "control_plane_events_secret" {
  type        = string
  description = "CONTROL_PLANE_EVENTS_SECRET (must match reconcile scheduler ControlPlaneSecret)."
  sensitive   = true
}

variable "control_plane_shadow_mode" {
  type        = bool
  description = "CONTROL_PLANE_SHADOW_MODE"
  default     = false
}

# Sizing
variable "cpu_architecture" {
  type        = string
  description = "Task CPU architecture (X86_64 or ARM64)."
  default     = "ARM64"
}

variable "api_cpu" {
  type        = string
  description = "API task CPU units."
  default     = "512"
}

variable "api_memory" {
  type        = string
  description = "API task memory (MiB)."
  default     = "1024"
}

variable "worker_cpu" {
  type        = string
  description = "Worker task CPU units."
  default     = "512"
}

variable "worker_memory" {
  type        = string
  description = "Worker task memory (MiB)."
  default     = "1024"
}

variable "api_desired_count" {
  type        = number
  description = "API service desired count."
  default     = 1
}

variable "worker_desired_count" {
  type        = number
  description = "Worker service desired count."
  default     = 1
}

