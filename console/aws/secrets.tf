# --- Secrets Manager ---

resource "aws_secretsmanager_secret" "app_secrets" {
  name                    = "${var.project_name}/${var.environment}/secrets"
  recovery_window_in_days = 0 # Allow immediate deletion for dev
}

resource "aws_secretsmanager_secret_version" "app_secrets" {
  secret_id = aws_secretsmanager_secret.app_secrets.id
  secret_string = jsonencode({
    LANGSMITH_API_KEY      = var.langsmith_api_key
    OPENAI_API_KEY         = var.openai_api_key
    ANTHROPIC_API_KEY      = var.anthropic_api_key
    SHOPIFY_ACCESS_TOKEN   = var.shopify_access_token
    STRIPE_SECRET_KEY      = var.stripe_secret_key
    PRINTFUL_API_KEY       = var.printful_api_key
    INSTAGRAM_ACCESS_TOKEN = var.instagram_access_token
  })
}
