#!/bin/bash

# AWS Configuration for data-pipelines PRODUCTION environment
# Covers orchestrator infra (DB, AWS creds) and shared ClickHouse destination.
# Per-connector secrets (Razorpay, Kapture, etc.) are managed dynamically
# via the orchestrator API when a connection is created.
#
# Usage: ./setup_aws_params_prod.sh

set -e

SERVICE_PREFIX="data-pipelines"  # prod has no suffix, consistent with IAMx convention
AWS_REGION="ap-south-1"

echo "Setting up AWS configuration for data-pipelines PRODUCTION environment..."
echo "  Prefix: ${SERVICE_PREFIX}"
echo ""
echo "WARNING: PRODUCTION ENVIRONMENT"
read -p "Type 'PROD' to confirm: " confirm
if [ "$confirm" != "PROD" ]; then
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
        --tags '[{"Key":"Service","Value":"data-pipelines"},{"Key":"Environment","Value":"prod"}]' \
        2>/dev/null \
        || aws secretsmanager update-secret \
            --region "${AWS_REGION}" \
            --secret-id "${SERVICE_PREFIX}.${key}" \
            --secret-string "${value}"
}

# =============================================================================
# Orchestrator — Database (RDS)
# =============================================================================

create_ssm_param "database.host"   "" "RDS host for data-pipelines"
create_ssm_param "database.port"   "5432"             "RDS port for data-pipelines"
create_ssm_param "database.name"   "" "RDS database name for data-pipelines"
create_ssm_param "database.user"   ""   "RDS user for data-pipelines"
# TODO: fill in before running
create_secret    "database.password" "" "RDS password for data-pipelines"

# =============================================================================
# Shared ClickHouse Destination
# =============================================================================

create_ssm_param "clickhouse.host"     "TODO" "ClickHouse host for data-pipelines"
create_ssm_param "clickhouse.port"     "9000" "ClickHouse port for data-pipelines"
create_ssm_param "clickhouse.database" "default" "ClickHouse database for data-pipelines"
create_ssm_param "clickhouse.user"     "default" "ClickHouse user for data-pipelines"
create_ssm_param "clickhouse.secure"   "true"    "ClickHouse TLS for data-pipelines"
# TODO: fill in before running
create_secret    "clickhouse.password" "" "ClickHouse password for data-pipelines"

# =============================================================================
# Orchestrator — Scheduler
# =============================================================================

create_ssm_param "scheduler.poll_interval_seconds" "30" "Job poll interval for data-pipelines"

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
