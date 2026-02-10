output "cloudfront_url" {
  description = "Forge Console URL (CloudFront)"
  value       = "https://${aws_cloudfront_distribution.frontend.domain_name}"
}

output "alb_url" {
  description = "ALB URL for API/WebSocket"
  value       = "http://${aws_lb.main.dns_name}"
}

output "ecr_forge_backend_url" {
  description = "ECR repository URL for forge-console backend"
  value       = aws_ecr_repository.forge_backend.repository_url
}

output "ecr_ecom_agents_url" {
  description = "ECR repository URL for ecom-agents"
  value       = aws_ecr_repository.ecom_agents.repository_url
}

output "s3_frontend_bucket" {
  description = "S3 bucket for frontend static files"
  value       = aws_s3_bucket.frontend.id
}

output "ecs_cluster_name" {
  description = "ECS cluster name"
  value       = aws_ecs_cluster.main.name
}

output "rds_endpoint" {
  description = "RDS PostgreSQL endpoint"
  value       = aws_db_instance.postgres.endpoint
}

output "redis_endpoint" {
  description = "ElastiCache Redis endpoint"
  value       = "${aws_elasticache_cluster.redis.cache_nodes[0].address}:${aws_elasticache_cluster.redis.cache_nodes[0].port}"
}

output "cloudfront_distribution_id" {
  description = "CloudFront distribution ID (for cache invalidation)"
  value       = aws_cloudfront_distribution.frontend.id
}
