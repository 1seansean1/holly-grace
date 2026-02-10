#!/usr/bin/env bash
# Forge Console — AWS Deployment Script
# Usage: ./deploy.sh [init|build|push|deploy|frontend|all|destroy]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
AWS_REGION="${AWS_REGION:-us-east-1}"

# Colors
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
log() { echo -e "${GREEN}[deploy]${NC} $*"; }
warn() { echo -e "${YELLOW}[warn]${NC} $*"; }
err() { echo -e "${RED}[error]${NC} $*" >&2; }

get_account_id() { aws sts get-caller-identity --query Account --output text; }
get_ecr_url() { echo "$(get_account_id).dkr.ecr.${AWS_REGION}.amazonaws.com"; }

cmd_init() {
    log "Initializing Terraform..."
    cd "$SCRIPT_DIR"
    terraform init
    log "Terraform initialized. Next: create terraform.tfvars with your secrets."
    echo ""
    echo "Example terraform.tfvars:"
    echo '  langsmith_api_key      = "lsv2_pt_..."'
    echo '  openai_api_key         = "sk-..."'
    echo '  anthropic_api_key      = "sk-ant-..."'
    echo '  shopify_access_token   = "shpat_..."'
    echo '  stripe_secret_key      = "sk_test_..."'
    echo '  printful_api_key       = "..."'
}

cmd_build() {
    log "Building Docker images..."

    # Build forge-console backend
    log "Building forge-console backend..."
    docker build -t forge-console/backend:latest "$PROJECT_ROOT/backend"

    # Build ecom-agents (needs its own Dockerfile)
    if [ -f "$PROJECT_ROOT/../ecom-agents/Dockerfile" ]; then
        log "Building ecom-agents..."
        docker build -t forge-console/ecom-agents:latest "$PROJECT_ROOT/../ecom-agents"
    else
        warn "ecom-agents Dockerfile not found at ../ecom-agents/Dockerfile"
        warn "You'll need to build and tag ecom-agents manually."
    fi

    log "Build complete."
}

cmd_push() {
    local ECR_URL
    ECR_URL="$(get_ecr_url)"

    log "Logging into ECR..."
    aws ecr get-login-password --region "$AWS_REGION" | docker login --username AWS --password-stdin "$ECR_URL"

    # Get repo URLs from Terraform output
    cd "$SCRIPT_DIR"
    local BACKEND_REPO ECR_AGENTS_REPO
    BACKEND_REPO=$(terraform output -raw ecr_forge_backend_url)
    ECR_AGENTS_REPO=$(terraform output -raw ecr_ecom_agents_url)

    log "Pushing forge-console backend..."
    docker tag forge-console/backend:latest "$BACKEND_REPO:latest"
    docker push "$BACKEND_REPO:latest"

    if docker image inspect forge-console/ecom-agents:latest >/dev/null 2>&1; then
        log "Pushing ecom-agents..."
        docker tag forge-console/ecom-agents:latest "$ECR_AGENTS_REPO:latest"
        docker push "$ECR_AGENTS_REPO:latest"
    else
        warn "ecom-agents image not found locally, skipping push."
    fi

    log "Push complete."
}

cmd_deploy() {
    log "Applying Terraform..."
    cd "$SCRIPT_DIR"
    terraform apply -auto-approve

    log "Forcing ECS service update..."
    local CLUSTER
    CLUSTER=$(terraform output -raw ecs_cluster_name)
    aws ecs update-service --cluster "$CLUSTER" --service forge-backend --force-new-deployment --region "$AWS_REGION" >/dev/null
    aws ecs update-service --cluster "$CLUSTER" --service ecom-agents --force-new-deployment --region "$AWS_REGION" >/dev/null

    log "Deployment initiated. Services will stabilize in ~2-3 minutes."
    echo ""
    terraform output
}

cmd_frontend() {
    log "Building frontend for production..."
    cd "$PROJECT_ROOT/frontend"

    # Get the ALB URL for API endpoint
    cd "$SCRIPT_DIR"
    local ALB_DNS
    ALB_DNS=$(terraform output -raw alb_url)

    cd "$PROJECT_ROOT/frontend"
    VITE_API_URL="$ALB_DNS" npm run build

    # Upload to S3
    local BUCKET
    cd "$SCRIPT_DIR"
    BUCKET=$(terraform output -raw s3_frontend_bucket)
    log "Uploading to S3 bucket: $BUCKET"
    aws s3 sync "$PROJECT_ROOT/frontend/dist" "s3://$BUCKET" --delete

    # Invalidate CloudFront cache
    local CF_ID
    CF_ID=$(terraform output -raw cloudfront_distribution_id)
    log "Invalidating CloudFront cache..."
    aws cloudfront create-invalidation --distribution-id "$CF_ID" --paths "/*" >/dev/null

    local CF_URL
    CF_URL=$(terraform output -raw cloudfront_url)
    log "Frontend deployed! URL: $CF_URL"
}

cmd_destroy() {
    warn "This will destroy ALL AWS resources for Forge Console."
    read -p "Are you sure? (yes/no): " confirm
    if [ "$confirm" = "yes" ]; then
        cd "$SCRIPT_DIR"
        # Empty S3 bucket first
        local BUCKET
        BUCKET=$(terraform output -raw s3_frontend_bucket 2>/dev/null || echo "")
        if [ -n "$BUCKET" ]; then
            aws s3 rm "s3://$BUCKET" --recursive 2>/dev/null || true
        fi
        terraform destroy -auto-approve
        log "All resources destroyed."
    else
        log "Cancelled."
    fi
}

cmd_all() {
    cmd_build
    cmd_deploy
    cmd_push
    # Force redeployment after push
    cmd_deploy
    cmd_frontend
    echo ""
    log "Full deployment complete!"
    cd "$SCRIPT_DIR"
    terraform output
}

# --- Main ---
case "${1:-help}" in
    init)     cmd_init ;;
    build)    cmd_build ;;
    push)     cmd_push ;;
    deploy)   cmd_deploy ;;
    frontend) cmd_frontend ;;
    all)      cmd_all ;;
    destroy)  cmd_destroy ;;
    *)
        echo "Usage: $0 {init|build|push|deploy|frontend|all|destroy}"
        echo ""
        echo "Commands:"
        echo "  init      Initialize Terraform and show tfvars template"
        echo "  build     Build Docker images locally"
        echo "  push      Push images to ECR"
        echo "  deploy    Apply Terraform + force ECS redeployment"
        echo "  frontend  Build frontend + upload to S3 + invalidate CloudFront"
        echo "  all       Full deployment (build + deploy + push + redeploy + frontend)"
        echo "  destroy   Tear down all AWS resources"
        ;;
esac
