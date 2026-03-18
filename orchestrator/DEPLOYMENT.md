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
- ECR repo: `767397958941.dkr.ecr.ap-south-1.amazonaws.com/orchestrator`
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
| Region | `ap-south-1` |
| ECR repo | `767397958941.dkr.ecr.ap-south-1.amazonaws.com/orchestrator` |
| Dev cluster | `arn:aws:eks:ap-south-1:767397958941:cluster/development` |
| Prod cluster | `arn:aws:eks:ap-south-1:767397958941:cluster/production` |
| Namespace | `services` |
| Dev domain | `orchestrator-api.goheartbeat.com` |
| Prod domain | `orchestrator-api.goheartbeat.app` |
| Dev IAM role | `arn:aws:iam::767397958941:role/orchestrator-dev-role` |
| Prod IAM role | `arn:aws:iam::767397958941:role/orchestrator-role` |

## Secrets

The orchestrator reads `database_url` from AWS Secrets Manager at runtime. The secret must exist at:

```
orchestrator/database_url
```

The pod has IAM permissions (via IRSA) to read any secret under the `orchestrator/*` path.

## k8s Structure

```
k8s/
├── base/               # shared manifests
└── overlays/
    ├── dev/            # dev overrides (1 replica, dev role, goheartbeat.com)
    └── prod/           # prod overrides (2 replicas, prod role, goheartbeat.app)
```
