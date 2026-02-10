variable "aws_region" {
  description = "AWS region for all resources"
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Project name used for resource naming"
  type        = string
  default     = "forge-console"
}

variable "environment" {
  description = "Deployment environment"
  type        = string
  default     = "production"
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "domain_name" {
  description = "Custom domain name (optional, leave empty to use CloudFront URL)"
  type        = string
  default     = ""
}

# --- ecom-agents configuration ---

variable "ecom_agents_image" {
  description = "ECR image URI for ecom-agents (set after first push)"
  type        = string
  default     = ""
}

variable "forge_backend_image" {
  description = "ECR image URI for forge-console backend (set after first push)"
  type        = string
  default     = ""
}

# --- Secrets (passed via terraform.tfvars or -var flags, never committed) ---

variable "langsmith_api_key" {
  description = "LangSmith API key"
  type        = string
  sensitive   = true
}

variable "openai_api_key" {
  description = "OpenAI API key"
  type        = string
  sensitive   = true
}

variable "anthropic_api_key" {
  description = "Anthropic API key"
  type        = string
  sensitive   = true
}

variable "shopify_access_token" {
  description = "Shopify access token"
  type        = string
  sensitive   = true
}

variable "stripe_secret_key" {
  description = "Stripe secret key"
  type        = string
  sensitive   = true
}

variable "printful_api_key" {
  description = "Printful API key"
  type        = string
  sensitive   = true
}

variable "instagram_access_token" {
  description = "Instagram access token"
  type        = string
  sensitive   = true
  default     = ""
}

# --- Sizing ---

variable "backend_cpu" {
  description = "CPU units for forge-console backend (1024 = 1 vCPU)"
  type        = number
  default     = 512
}

variable "backend_memory" {
  description = "Memory (MB) for forge-console backend"
  type        = number
  default     = 1024
}

variable "ecom_agents_cpu" {
  description = "CPU units for ecom-agents"
  type        = number
  default     = 512
}

variable "ecom_agents_memory" {
  description = "Memory (MB) for ecom-agents"
  type        = number
  default     = 1024
}

variable "db_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t4g.micro"
}

variable "redis_node_type" {
  description = "ElastiCache node type"
  type        = string
  default     = "cache.t4g.micro"
}
