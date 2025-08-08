#!/bin/bash

# Production Secrets Deployment Script
# Deploys and manages secrets for the AI Enhanced PDF Scholar system
# with zero-downtime rotation and comprehensive security validation

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
K8S_MANIFESTS_DIR="$PROJECT_ROOT/k8s/manifests"
BACKUP_DIR="$HOME/.ai_pdf_scholar/secrets_backups"
LOG_FILE="/var/log/ai-pdf-scholar-secrets-deploy.log"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Default values
ENVIRONMENT="production"
DRY_RUN=false
FORCE=false
BACKUP_BEFORE_DEPLOY=true
VALIDATE_SECRETS=true
KUBECTL_CONTEXT=""
NAMESPACE="ai-pdf-scholar"
SECRETS_MANAGER_IMAGE="ai-pdf-scholar/secrets-manager:latest"

# Logging function
log() {
    local level=$1
    shift
    local message="$*"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    
    case $level in
        "INFO")
            echo -e "${GREEN}[INFO]${NC} $message"
            ;;
        "WARN")
            echo -e "${YELLOW}[WARN]${NC} $message"
            ;;
        "ERROR")
            echo -e "${RED}[ERROR]${NC} $message"
            ;;
        "DEBUG")
            echo -e "${BLUE}[DEBUG]${NC} $message"
            ;;
    esac
    
    echo "[$timestamp] [$level] $message" >> "$LOG_FILE"
}

# Print usage
usage() {
    cat << EOF
Usage: $0 [OPTIONS] COMMAND

Production secrets deployment and management script for AI Enhanced PDF Scholar

COMMANDS:
    deploy              Deploy secrets to Kubernetes
    rotate              Rotate secrets (with zero-downtime)
    backup              Create encrypted backup of secrets
    restore             Restore secrets from backup
    validate            Validate secrets compliance
    health-check        Check secrets system health
    generate            Generate new secrets
    clean               Clean up old secrets and backups

OPTIONS:
    -e, --environment ENV       Environment (production|staging|development) [default: production]
    -n, --namespace NAMESPACE   Kubernetes namespace [default: ai-pdf-scholar]
    -c, --context CONTEXT       Kubectl context to use
    -i, --image IMAGE           Secrets manager Docker image [default: ai-pdf-scholar/secrets-manager:latest]
    --dry-run                   Show what would be done without making changes
    --force                     Force operation even if validation fails
    --no-backup                 Skip backup before deployment
    --no-validate               Skip secrets validation
    -v, --verbose               Enable verbose output
    -h, --help                  Show this help message

EXAMPLES:
    # Deploy secrets to production
    $0 deploy -e production

    # Rotate specific secret
    $0 rotate database_password -e production

    # Backup all secrets
    $0 backup -e production

    # Validate secrets compliance
    $0 validate -e production

    # Health check
    $0 health-check

    # Generate new secrets for staging
    $0 generate -e staging

ENVIRONMENT VARIABLES:
    SECRETS_ENCRYPTION_KEY      Master encryption key (required)
    VAULT_TOKEN                 HashiCorp Vault token (if using Vault)
    AWS_ACCESS_KEY_ID           AWS access key (if using AWS Secrets Manager)
    AWS_SECRET_ACCESS_KEY       AWS secret key (if using AWS Secrets Manager)
    KUBECTL_CONTEXT             Default kubectl context
    SECRETS_BACKUP_S3_BUCKET    S3 bucket for backup storage

EOF
}

# Check prerequisites
check_prerequisites() {
    log "INFO" "Checking prerequisites..."
    
    local missing_tools=()
    
    # Check required tools
    command -v kubectl >/dev/null 2>&1 || missing_tools+=("kubectl")
    command -v python3 >/dev/null 2>&1 || missing_tools+=("python3")
    command -v openssl >/dev/null 2>&1 || missing_tools+=("openssl")
    command -v jq >/dev/null 2>&1 || missing_tools+=("jq")
    
    if [[ ${#missing_tools[@]} -gt 0 ]]; then
        log "ERROR" "Missing required tools: ${missing_tools[*]}"
        log "ERROR" "Please install the missing tools and try again"
        exit 1
    fi
    
    # Check kubectl context
    if [[ -n "$KUBECTL_CONTEXT" ]]; then
        if ! kubectl config use-context "$KUBECTL_CONTEXT" >/dev/null 2>&1; then
            log "ERROR" "Failed to set kubectl context: $KUBECTL_CONTEXT"
            exit 1
        fi
    fi
    
    # Check namespace exists
    if ! kubectl get namespace "$NAMESPACE" >/dev/null 2>&1; then
        log "WARN" "Namespace $NAMESPACE does not exist, creating it..."
        if [[ "$DRY_RUN" == "false" ]]; then
            kubectl create namespace "$NAMESPACE"
        fi
    fi
    
    # Create backup directory
    mkdir -p "$BACKUP_DIR"
    
    log "INFO" "Prerequisites check completed"
}

# Generate secure secrets
generate_secrets() {
    log "INFO" "Generating secure secrets for environment: $ENVIRONMENT"
    
    local secrets_file="$PROJECT_ROOT/secrets_generated_${ENVIRONMENT}.yaml"
    
    # Use Python script to generate secrets
    python3 << EOF
import secrets
import base64
import json
import string
from datetime import datetime

def generate_password(length=32):
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def generate_key(bits=256):
    return base64.b64encode(secrets.token_bytes(bits // 8)).decode('utf-8')

def generate_jwt_secret(bits=256):
    return base64.urlsafe_b64encode(secrets.token_bytes(bits // 8)).decode('utf-8').rstrip('=')

# Generate all secrets
generated_secrets = {
    'POSTGRES_PASSWORD': generate_password(32),
    'REDIS_PASSWORD': generate_password(32),
    'JWT_SECRET_KEY': generate_jwt_secret(256),
    'JWT_REFRESH_SECRET_KEY': generate_jwt_secret(256),
    'MASTER_ENCRYPTION_KEY': generate_key(512),
    'DATA_ENCRYPTION_KEY': generate_key(256),
    'FIELD_ENCRYPTION_KEY': generate_key(256),
    'SESSION_SECRET': generate_key(256),
    'CSRF_SECRET': generate_key(256),
    'AUDIT_LOG_SIGNING_KEY': generate_key(256),
    'WEBHOOK_SECRET': generate_key(256),
    'BACKUP_ENCRYPTION_KEY': generate_key(256),
    'BACKUP_SIGNING_KEY': generate_key(256),
    'postgres-password': generate_password(32),
    'password': generate_password(32),
    'replication-password': generate_password(32),
    'readonly-password': generate_password(32),
    'redis-password': generate_password(32),
    'sentinel-password': generate_password(32)
}

# Save to JSON file for processing
with open('$PROJECT_ROOT/generated_secrets.json', 'w') as f:
    json.dump(generated_secrets, f, indent=2)

print("Generated secrets for $ENVIRONMENT environment")
EOF
    
    if [[ $? -eq 0 ]]; then
        log "INFO" "Secrets generation completed"
        if [[ "$DRY_RUN" == "false" ]]; then
            log "INFO" "Generated secrets saved to: $PROJECT_ROOT/generated_secrets.json"
            log "WARN" "Remember to securely delete the generated secrets file after deployment"
        fi
    else
        log "ERROR" "Failed to generate secrets"
        exit 1
    fi
}

# Validate secrets
validate_secrets() {
    log "INFO" "Validating secrets for environment: $ENVIRONMENT"
    
    # Call the secrets validation API endpoint
    local validation_result
    if command -v curl >/dev/null 2>&1; then
        # Assuming the service is running locally for validation
        validation_result=$(curl -s -X POST \
            "http://localhost:8000/system/secrets/validate" \
            -H "Content-Type: application/json" \
            -d "{\"environment\": \"$ENVIRONMENT\", \"compliance_standards\": [\"nist_800_53\", \"iso_27001\", \"soc2_type2\"]}" \
            2>/dev/null || echo '{"status": "error", "message": "API not available"}')
    else
        log "WARN" "curl not available, skipping API validation"
        return 0
    fi
    
    # Parse validation result
    local status=$(echo "$validation_result" | jq -r '.data.compliance_report.summary.overall_status // "unknown"')
    
    case "$status" in
        "compliant")
            log "INFO" "✅ Secrets validation passed - all secrets are compliant"
            return 0
            ;;
        "partially_compliant")
            log "WARN" "⚠️  Secrets validation warning - some issues found"
            if [[ "$FORCE" == "false" ]]; then
                log "ERROR" "Use --force to proceed with warnings"
                return 1
            fi
            ;;
        "non_compliant")
            log "ERROR" "❌ Secrets validation failed - critical issues found"
            if [[ "$FORCE" == "false" ]]; then
                return 1
            fi
            log "WARN" "Proceeding with --force flag despite validation errors"
            ;;
        *)
            log "WARN" "Unable to validate secrets - API may not be available"
            if [[ "$FORCE" == "false" ]]; then
                log "ERROR" "Use --force to proceed without validation"
                return 1
            fi
            ;;
    esac
    
    return 0
}

# Create backup
create_backup() {
    log "INFO" "Creating backup of existing secrets..."
    
    local backup_timestamp=$(date '+%Y%m%d_%H%M%S')
    local backup_file="$BACKUP_DIR/secrets_backup_${ENVIRONMENT}_${backup_timestamp}.tar.gz"
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log "INFO" "[DRY RUN] Would create backup: $backup_file"
        return 0
    fi
    
    # Export existing secrets
    local temp_dir=$(mktemp -d)
    
    # Get all secret names for this environment
    local secret_names=("ai-pdf-scholar-secrets" "postgresql-secrets" "redis-secrets" "external-services-secrets")
    
    for secret_name in "${secret_names[@]}"; do
        if kubectl get secret "$secret_name" -n "$NAMESPACE" >/dev/null 2>&1; then
            kubectl get secret "$secret_name" -n "$NAMESPACE" -o yaml > "$temp_dir/${secret_name}.yaml"
            log "DEBUG" "Exported secret: $secret_name"
        fi
    done
    
    # Create encrypted backup
    if [[ -n "${SECRETS_ENCRYPTION_KEY:-}" ]]; then
        tar czf - -C "$temp_dir" . | openssl enc -aes-256-cbc -salt -k "$SECRETS_ENCRYPTION_KEY" > "$backup_file"
    else
        tar czf "$backup_file" -C "$temp_dir" .
        log "WARN" "Backup created without encryption (SECRETS_ENCRYPTION_KEY not set)"
    fi
    
    # Cleanup temp directory
    rm -rf "$temp_dir"
    
    if [[ -f "$backup_file" ]]; then
        log "INFO" "✅ Backup created successfully: $backup_file"
        
        # Upload to S3 if configured
        if [[ -n "${SECRETS_BACKUP_S3_BUCKET:-}" ]] && command -v aws >/dev/null 2>&1; then
            log "INFO" "Uploading backup to S3..."
            aws s3 cp "$backup_file" "s3://$SECRETS_BACKUP_S3_BUCKET/backups/"
            log "INFO" "✅ Backup uploaded to S3"
        fi
    else
        log "ERROR" "Failed to create backup"
        return 1
    fi
}

# Deploy secrets
deploy_secrets() {
    log "INFO" "Deploying secrets to environment: $ENVIRONMENT"
    
    # Backup existing secrets if requested
    if [[ "$BACKUP_BEFORE_DEPLOY" == "true" ]]; then
        create_backup
    fi
    
    # Validate secrets if requested
    if [[ "$VALIDATE_SECRETS" == "true" ]]; then
        validate_secrets || return 1
    fi
    
    # Process secrets manifest
    local secrets_manifest="$K8S_MANIFESTS_DIR/secrets.yaml"
    local processed_manifest=$(mktemp)
    
    # Replace placeholder values with generated secrets if available
    if [[ -f "$PROJECT_ROOT/generated_secrets.json" ]]; then
        log "INFO" "Applying generated secrets to manifest..."
        
        # Use Python to process the manifest with generated secrets
        python3 << EOF
import json
import sys
import re

# Load generated secrets
with open('$PROJECT_ROOT/generated_secrets.json', 'r') as f:
    secrets = json.load(f)

# Read manifest
with open('$secrets_manifest', 'r') as f:
    manifest_content = f.read()

# Replace placeholders
for key, value in secrets.items():
    # Match patterns like GENERATED_* or REPLACE_WITH_*
    patterns = [
        f'GENERATED_{key.upper()}_.*',
        f'REPLACE_WITH_{key.upper()}_.*',
        f'GENERATED_.*_{key.upper()}.*',
        f'REPLACE_WITH_.*_{key.upper()}.*'
    ]
    
    for pattern in patterns:
        manifest_content = re.sub(pattern, value, manifest_content)

# Write processed manifest
with open('$processed_manifest', 'w') as f:
    f.write(manifest_content)

print("Manifest processed with generated secrets")
EOF
    else
        cp "$secrets_manifest" "$processed_manifest"
        log "WARN" "No generated secrets found, using manifest as-is"
    fi
    
    # Apply secrets to Kubernetes
    if [[ "$DRY_RUN" == "true" ]]; then
        log "INFO" "[DRY RUN] Would apply secrets manifest:"
        kubectl apply -f "$processed_manifest" -n "$NAMESPACE" --dry-run=client
    else
        log "INFO" "Applying secrets to Kubernetes..."
        kubectl apply -f "$processed_manifest" -n "$NAMESPACE"
        
        if [[ $? -eq 0 ]]; then
            log "INFO" "✅ Secrets deployed successfully"
            
            # Wait for secrets to be available
            log "INFO" "Waiting for secrets to be ready..."
            sleep 5
            
            # Verify secrets are accessible
            verify_secrets_deployment
        else
            log "ERROR" "❌ Failed to deploy secrets"
            return 1
        fi
    fi
    
    # Cleanup processed manifest
    rm -f "$processed_manifest"
    
    # Cleanup generated secrets file for security
    if [[ -f "$PROJECT_ROOT/generated_secrets.json" && "$DRY_RUN" == "false" ]]; then
        log "INFO" "Cleaning up generated secrets file..."
        shred -u "$PROJECT_ROOT/generated_secrets.json" 2>/dev/null || rm -f "$PROJECT_ROOT/generated_secrets.json"
    fi
}

# Verify secrets deployment
verify_secrets_deployment() {
    log "INFO" "Verifying secrets deployment..."
    
    local secret_names=("ai-pdf-scholar-secrets" "postgresql-secrets" "redis-secrets")
    local failed_secrets=()
    
    for secret_name in "${secret_names[@]}"; do
        if kubectl get secret "$secret_name" -n "$NAMESPACE" >/dev/null 2>&1; then
            log "DEBUG" "✅ Secret verified: $secret_name"
        else
            log "ERROR" "❌ Secret not found: $secret_name"
            failed_secrets+=("$secret_name")
        fi
    done
    
    if [[ ${#failed_secrets[@]} -eq 0 ]]; then
        log "INFO" "✅ All secrets verified successfully"
        return 0
    else
        log "ERROR" "❌ Failed to verify secrets: ${failed_secrets[*]}"
        return 1
    fi
}

# Rotate secrets
rotate_secrets() {
    local secret_name="${1:-all}"
    
    log "INFO" "Rotating secrets: $secret_name"
    
    if [[ "$secret_name" == "all" ]]; then
        log "INFO" "Rotating all secrets..."
        # Generate new secrets
        generate_secrets
        # Deploy with new secrets
        deploy_secrets
    else
        log "INFO" "Rotating specific secret: $secret_name"
        
        # Call the rotation API endpoint
        if command -v curl >/dev/null 2>&1; then
            local rotation_result
            rotation_result=$(curl -s -X POST \
                "http://localhost:8000/system/secrets/rotate/$secret_name" \
                -H "Content-Type: application/json" \
                2>/dev/null || echo '{"status": "error", "message": "API not available"}')
            
            local status=$(echo "$rotation_result" | jq -r '.message // "unknown"')
            log "INFO" "Rotation result: $status"
        else
            log "ERROR" "curl not available, cannot perform individual secret rotation"
            return 1
        fi
    fi
}

# Health check
health_check() {
    log "INFO" "Performing secrets health check..."
    
    # Check if secrets exist in Kubernetes
    local k8s_health="healthy"
    local secret_names=("ai-pdf-scholar-secrets" "postgresql-secrets" "redis-secrets")
    
    for secret_name in "${secret_names[@]}"; do
        if ! kubectl get secret "$secret_name" -n "$NAMESPACE" >/dev/null 2>&1; then
            log "ERROR" "Secret not found: $secret_name"
            k8s_health="unhealthy"
        fi
    done
    
    # Check API health if available
    local api_health="unknown"
    if command -v curl >/dev/null 2>&1; then
        local health_result
        health_result=$(curl -s -X GET \
            "http://localhost:8000/system/health/secrets" \
            -H "Content-Type: application/json" \
            2>/dev/null || echo '{"status": "error", "message": "API not available"}')
        
        api_health=$(echo "$health_result" | jq -r '.data.overall_status // "unknown"')
    fi
    
    # Summary
    log "INFO" "Health Check Results:"
    log "INFO" "  Kubernetes Secrets: $k8s_health"
    log "INFO" "  API Health: $api_health"
    
    if [[ "$k8s_health" == "healthy" && "$api_health" =~ ^(healthy|unknown)$ ]]; then
        log "INFO" "✅ Overall health: HEALTHY"
        return 0
    else
        log "ERROR" "❌ Overall health: UNHEALTHY"
        return 1
    fi
}

# Clean up old backups and rotated secrets
cleanup() {
    log "INFO" "Cleaning up old backups and secrets..."
    
    # Clean up old backups (keep last 30 days)
    if [[ -d "$BACKUP_DIR" ]]; then
        log "INFO" "Cleaning backups older than 30 days..."
        find "$BACKUP_DIR" -name "secrets_backup_*.tar.gz" -mtime +30 -delete 2>/dev/null || true
    fi
    
    # Clean up temporary files
    find /tmp -name "secrets_*" -mtime +1 -delete 2>/dev/null || true
    
    log "INFO" "✅ Cleanup completed"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -e|--environment)
            ENVIRONMENT="$2"
            shift 2
            ;;
        -n|--namespace)
            NAMESPACE="$2"
            shift 2
            ;;
        -c|--context)
            KUBECTL_CONTEXT="$2"
            shift 2
            ;;
        -i|--image)
            SECRETS_MANAGER_IMAGE="$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --force)
            FORCE=true
            shift
            ;;
        --no-backup)
            BACKUP_BEFORE_DEPLOY=false
            shift
            ;;
        --no-validate)
            VALIDATE_SECRETS=false
            shift
            ;;
        -v|--verbose)
            set -x
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            break
            ;;
    esac
done

# Get command
COMMAND="${1:-}"

# Validate environment
case "$ENVIRONMENT" in
    production|staging|development)
        ;;
    *)
        log "ERROR" "Invalid environment: $ENVIRONMENT"
        log "ERROR" "Valid environments: production, staging, development"
        exit 1
        ;;
esac

# Create log file directory
mkdir -p "$(dirname "$LOG_FILE")"

# Main execution
log "INFO" "Starting secrets deployment script"
log "INFO" "Environment: $ENVIRONMENT"
log "INFO" "Namespace: $NAMESPACE"
log "INFO" "Dry run: $DRY_RUN"

# Check prerequisites
check_prerequisites

# Execute command
case "$COMMAND" in
    deploy)
        deploy_secrets
        ;;
    rotate)
        rotate_secrets "${2:-all}"
        ;;
    backup)
        create_backup
        ;;
    validate)
        validate_secrets
        ;;
    health-check)
        health_check
        ;;
    generate)
        generate_secrets
        ;;
    clean)
        cleanup
        ;;
    "")
        log "ERROR" "No command specified"
        usage
        exit 1
        ;;
    *)
        log "ERROR" "Unknown command: $COMMAND"
        usage
        exit 1
        ;;
esac

log "INFO" "Secrets deployment script completed successfully"