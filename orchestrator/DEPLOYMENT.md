# Orchestrator Deployment

## Prerequisites

- AWS CLI configured with valid credentials (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`)
- MFA enabled on your IAM user
- Docker with buildx
- `kubectl` with access to the EKS clusters
- `kustomize` (or `kubectl` ≥ 1.14)

## One-time Setup

Run once to create the ECR repository and IAM roles for both environments:

```sh
make orchestrator-setup-iam
```

This creates:
- ECR repo: `<YOUR_AWS_ACCOUNT_ID>.dkr.ecr.<YOUR_AWS_REGION>.amazonaws.com/orchestrator`
- IAM policy: `orchestrator-policy` (Secrets Manager read access)
- IAM roles: `orchestrator-dev-role`, `orchestrator-role` (IRSA for EKS pods)

## Deploy

```sh
make orchestrator-deploy ENV=dev
make orchestrator-deploy ENV=prod   # must be on main branch
```

This will:
1. Prompt for MFA token if credentials are expired
2. Build and push the Docker image to ECR
3. Apply the k8s manifests via kustomize
4. Wait for the rollout to complete

## Other Commands

```sh
# Re-apply manifests without rebuilding the image
make orchestrator-deploy-only ENV=dev

# Preview rendered manifests before applying
make orchestrator-preview ENV=dev

# Rollback to the previous deployment
make orchestrator-rollback ENV=dev

# Check pod and deployment status
make orchestrator-status ENV=dev
```

## AWS Auth

Credentials are read from environment variables. If they are expired, `make` will automatically detect this, look up your MFA device, and prompt for a token code before proceeding.

Ensure these are set in your shell before running any target:

```sh
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...
```

## Infrastructure

| Resource | Value |
|---|---|
| Region | `<YOUR_AWS_REGION>` |
| ECR repo | `<YOUR_AWS_ACCOUNT_ID>.dkr.ecr.<YOUR_AWS_REGION>.amazonaws.com/orchestrator` |
| Dev cluster | `arn:aws:eks:<YOUR_AWS_REGION>:<YOUR_AWS_ACCOUNT_ID>:cluster/development` |
| Prod cluster | `arn:aws:eks:<YOUR_AWS_REGION>:<YOUR_AWS_ACCOUNT_ID>:cluster/production` |
| Namespace | `services` |
| Dev domain | `orchestrator-api.<YOUR_DEV_DOMAIN>` |
| Prod domain | `orchestrator-api.<YOUR_PROD_DOMAIN>` |
| Dev IAM role | `arn:aws:iam::<YOUR_AWS_ACCOUNT_ID>:role/orchestrator-dev-role` |
| Prod IAM role | `arn:aws:iam::<YOUR_AWS_ACCOUNT_ID>:role/orchestrator-role` |

## Secrets / Config

The orchestrator fetches config from SSM Parameter Store and Secrets Manager at startup using the `AWS_PARAM_PREFIX` path.

| Key | Store | Dev path | Prod path |
|---|---|---|---|
| `database.host` | SSM | `turbocat-dev.database.host` | `turbocat.database.host` |
| `database.port` | SSM | `turbocat-dev.database.port` | `turbocat.database.port` |
| `database.user` | SSM | `turbocat-dev.database.user` | `turbocat.database.user` |
| `database.name` | SSM | `turbocat-dev.database.name` | `turbocat.database.name` |
| `database.password` | Secrets Manager | `turbocat-dev.database.password` | `turbocat.database.password` |
| `scheduler.poll_interval_seconds` | SSM | `turbocat-dev.scheduler.poll_interval_seconds` | `turbocat.scheduler.poll_interval_seconds` |

The pod has IAM permissions (via IRSA) to read from the `turbocat-dev.*` (dev) and `turbocat.*` (prod) paths.

## k8s Structure

```
k8s/
├── base/               # shared manifests
└── overlays/
    ├── dev/            # dev overrides (1 replica, dev role)
    └── prod/           # prod overrides (2 replicas, prod role)
```
