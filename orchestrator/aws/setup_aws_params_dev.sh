#!/bin/bash

# AWS Configuration for data-pipelines DEV environment
# Covers orchestrator infra (DB, AWS creds) and shared ClickHouse destination.
# Per-connector secrets (Razorpay, Kapture, etc.) are managed dynamically
# via the orchestrator API when a connection is created.
#
# Usage: ./setup_aws_params_dev.sh

set -e

SERVICE_PREFIX="data-pipelines-dev"
AWS_REGION="ap-south-1"

echo "Setting up AWS configuration for data-pipelines DEV environment..."
echo "  Prefix: ${SERVICE_PREFIX}"
echo ""
read -p "This will overwrite existing parameters. Continue? (yes/no): " confirm
if [ "$confirm" != "yes" ]; then
    echo "Aborted."
    exit 1
fi

# =============================================================================
# Utility Functions
# =============================================================================

create_ssm_param() {
    local key=$1
    local value=$2
    local description=$3

    if [ -z "$value" ]; then
        echo "  Skipping empty value for ${SERVICE_PREFIX}.${key}"
        return
    fi

    echo "  SSM: ${SERVICE_PREFIX}.${key}"
    aws ssm put-parameter \
        --name "${SERVICE_PREFIX}.${key}" \
        --value "${value}" \
        --type "String" \
        --description "${description}" \
        --region "${AWS_REGION}" \
        --overwrite
}

create_secret() {
    local key=$1
    local value=$2
    local description=$3

    if [ -z "$value" ]; then
        echo "  Skipping empty value for ${SERVICE_PREFIX}.${key}"
        return
    fi

    echo "  Secret: ${SERVICE_PREFIX}.${key}"
    aws secretsmanager create-secret \
        --name "${SERVICE_PREFIX}.${key}" \
        --secret-string "${value}" \
        --description "${description}" \
        --region "${AWS_REGION}" \
        --tags '[{"Key":"Service","Value":"data-pipelines"},{"Key":"Environment","Value":"dev"}]' \
        2>/dev/null \
        || aws secretsmanager update-secret \
            --region "${AWS_REGION}" \
            --secret-id "${SERVICE_PREFIX}.${key}" \
            --secret-string "${value}"
}

# =============================================================================
# Orchestrator — Database (RDS)
# Non-sensitive fields in SSM, password in Secrets Manager.
# At deploy time, DATABASE_URL is assembled from these or injected directly.
# =============================================================================

create_ssm_param "database.host"   "" "RDS host for data-pipelines (DEV)"
create_ssm_param "database.port"   "5432"             "RDS port for data-pipelines (DEV)"
create_ssm_param "database.name"   "" "RDS database name for data-pipelines (DEV)"
create_ssm_param "database.user"   ""   "RDS user for data-pipelines (DEV)"
# TODO: fill in before running
create_secret    "database.password" "" "RDS password for data-pipelines (DEV)"

# =============================================================================
# Shared ClickHouse Destination
# =============================================================================

create_ssm_param "clickhouse.host"     "localhost"  "ClickHouse host for data-pipelines (DEV)"
create_ssm_param "clickhouse.port"     "9000"       "ClickHouse port for data-pipelines (DEV)"
create_ssm_param "clickhouse.database" "default"    "ClickHouse database for data-pipelines (DEV)"
create_ssm_param "clickhouse.user"     "default"    "ClickHouse user for data-pipelines (DEV)"
create_ssm_param "clickhouse.secure"   "false"      "ClickHouse TLS for data-pipelines (DEV)"
# TODO: fill in before running
create_secret    "clickhouse.password" "" "ClickHouse password for data-pipelines (DEV)"

# =============================================================================
# Orchestrator — Scheduler
# =============================================================================

create_ssm_param "scheduler.poll_interval_seconds" "30" "Job poll interval for data-pipelines (DEV)"

# =============================================================================
# Orchestrator — Auth
# JWT secret stored in Secrets Manager (sensitive). Algorithm and CORS in SSM.
# Generate secret with: python -c "import secrets; print(secrets.token_hex(32))"
# =============================================================================

# TODO: fill in before running
create_secret    "auth.jwt_secret"    "" "JWT signing secret for data-pipelines (DEV)"
create_ssm_param "auth.jwt_algorithm" "HS256" "JWT algorithm for data-pipelines (DEV)"
create_secret    "auth.agent_api_key" "" "Agent shared API key for data-pipelines (DEV)"
create_ssm_param "auth.cors_origins"  "*"     "Allowed CORS origins for data-pipelines (DEV)"

# =============================================================================
# Summary
# =============================================================================

echo ""
echo "Done. SSM parameters:"
aws ssm describe-parameters \
    --region "${AWS_REGION}" \
    --filters "Key=Name,Values=${SERVICE_PREFIX}" \
    --query 'Parameters[].Name' \
    --output table

echo ""
echo "Secrets:"
aws secretsmanager list-secrets \
    --region "${AWS_REGION}" \
    --filters "Key=name,Values=${SERVICE_PREFIX}" \
    --query 'SecretList[].Name' \
    --output table
