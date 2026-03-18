# AWS Setup

Scripts to push orchestrator config to SSM Parameter Store and Secrets Manager.

> Per-connector secrets (Razorpay, Kapture, etc.) are **not** managed here —
> they are stored dynamically via the orchestrator API when a connection is created.

## Scripts

| Script | Environment | SSM prefix |
|--------|-------------|------------|
| `setup_aws_params_dev.sh` | DEV | `data-pipelines-dev.*` |
| `setup_aws_params_prod.sh` | PROD | `data-pipelines.*` |

## Prerequisites

### 1. AWS CLI installed

```bash
brew install awscli
```

### 2. AWS profile configured

Add your credentials to `~/.aws/credentials`:

```ini
[<profile-name>]
aws_access_key_id = <your-key>
aws_secret_access_key = <your-secret>
```

And in `~/.aws/config`:

```ini
[profile <profile-name>]
region = ap-south-1
mfa_serial = <your-mfa-device-arn>
```

To find your MFA device ARN:

```bash
aws iam list-mfa-devices --profile <profile-name>
```

### 3. Authenticate with MFA

Our AWS account has a `ForceMFA` policy — all API calls are blocked until you have
a valid session token. Do this once per session (lasts 12 hours):

```bash
aws sts get-session-token \
  --serial-number <your-mfa-device-arn> \
  --token-code <6-digit-code-from-authenticator> \
  --profile <profile-name>
```

Export the returned credentials:

```bash
export AWS_ACCESS_KEY_ID=<AccessKeyId>
export AWS_SECRET_ACCESS_KEY=<SecretAccessKey>
export AWS_SESSION_TOKEN=<SessionToken>
```

Verify it worked:

```bash
aws sts get-caller-identity
```

## Running the scripts

Fill in any `TODO` values in the script first (DB password, ClickHouse password),
then run:

```bash
# DEV
./aws/setup_aws_params_dev.sh

# PROD
./aws/setup_aws_params_prod.sh
```

The scripts skip any empty-string values, so they won't overwrite existing secrets
with blanks if you leave a TODO unfilled.

## What gets created

| Parameter | Type | Notes |
|-----------|------|-------|
| `{prefix}.database.host` | SSM | RDS hostname |
| `{prefix}.database.port` | SSM | |
| `{prefix}.database.name` | SSM | |
| `{prefix}.database.user` | SSM | |
| `{prefix}.database.password` | Secret | Sensitive |
| `{prefix}.clickhouse.host` | SSM | |
| `{prefix}.clickhouse.port` | SSM | |
| `{prefix}.clickhouse.database` | SSM | |
| `{prefix}.clickhouse.user` | SSM | |
| `{prefix}.clickhouse.secure` | SSM | |
| `{prefix}.clickhouse.password` | Secret | Sensitive |
| `{prefix}.scheduler.poll_interval_seconds` | SSM | |

## How the orchestrator uses these

Set `CONFIG_PROVIDER=aws` and `AWS_PARAM_PREFIX=data-pipelines-dev` (or `data-pipelines`
for prod) in the ECS task definition. The orchestrator fetches all params at startup
and assembles `DATABASE_URL` — no `.env` file needed in deployed environments.

On ECS, no explicit AWS credentials are required — the task IAM role is used automatically.
