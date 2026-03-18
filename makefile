.ONESHELL:
SHELL := /bin/bash

.PHONY: connectors-setup connectors-test connectors-lint connectors-format \
	orchestrator-setup-iam orchestrator-ecr-login orchestrator-build orchestrator-push \
	orchestrator-deploy orchestrator-deploy-only orchestrator-preview orchestrator-rollback orchestrator-status

# ── Config ────────────────────────────────────────────────────
AWS_REGION   ?= ap-south-1
AWS_ACCOUNT  := 767397958941
ORCHESTRATOR := orchestrator
IMAGE        := $(AWS_ACCOUNT).dkr.ecr.$(AWS_REGION).amazonaws.com/$(ORCHESTRATOR)
K8S_DIR      := orchestrator/k8s
AWS_DIR      := orchestrator/aws
GIT_SHA      := $(shell git rev-parse --short HEAD 2>/dev/null || echo unknown)
GIT_BRANCH   := $(shell git rev-parse --abbrev-ref HEAD 2>/dev/null || echo unknown)
PLATFORM     ?= linux/amd64
ENV          ?=

KUBE_CONTEXT := $(if $(filter dev,$(ENV)),arn:aws:eks:$(AWS_REGION):$(AWS_ACCOUNT):cluster/development,\
                $(if $(filter prod,$(ENV)),arn:aws:eks:$(AWS_REGION):$(AWS_ACCOUNT):cluster/production,))

# ── Connectors ────────────────────────────────────────────────
connectors-setup:
	cd connectors && make setup

connectors-test:
	cd connectors && make test

connectors-lint:
	cd connectors && make lint

connectors-format:
	cd connectors && make format

# ── Orchestrator: ECR login (handles MFA if needed) ───────────
# All targets that need AWS go through this first.
orchestrator-ecr-login:
	@if ! aws sts get-caller-identity > /dev/null 2>&1; then
		echo "[INFO] AWS credentials expired or missing. Initiating MFA session..."
		MFA_SERIAL=$$(aws iam list-mfa-devices --query 'MFADevices[0].SerialNumber' --output text 2>/dev/null)
		if [ -z "$$MFA_SERIAL" ] || [ "$$MFA_SERIAL" = "None" ]; then
			echo "[ERROR] No MFA device found for current IAM user."; exit 1
		fi
		echo "[INFO] MFA device: $$MFA_SERIAL"
		printf "Enter MFA token code: "; read MFA_CODE
		STS=$$(aws sts get-session-token --serial-number $$MFA_SERIAL --token-code $$MFA_CODE --duration-seconds 43200 2>&1)
		if [ $$? -ne 0 ]; then echo "[ERROR] $$STS"; exit 1; fi
		export AWS_ACCESS_KEY_ID=$$(echo "$$STS" | python3 -c "import sys,json; print(json.load(sys.stdin)['Credentials']['AccessKeyId'])")
		export AWS_SECRET_ACCESS_KEY=$$(echo "$$STS" | python3 -c "import sys,json; print(json.load(sys.stdin)['Credentials']['SecretAccessKey'])")
		export AWS_SESSION_TOKEN=$$(echo "$$STS" | python3 -c "import sys,json; print(json.load(sys.stdin)['Credentials']['SessionToken'])")
		echo "[SUCCESS] MFA session established (valid 12h)."
	else
		echo "[INFO] AWS credentials valid."
	fi
	aws ecr get-login-password --region $(AWS_REGION) | \
		docker login --username AWS --password-stdin $(AWS_ACCOUNT).dkr.ecr.$(AWS_REGION).amazonaws.com

# ── Orchestrator: one-time AWS setup ──────────────────────────
# Run once before first deploy: make orchestrator-setup-iam
orchestrator-setup-iam:
	@if ! aws sts get-caller-identity > /dev/null 2>&1; then
		echo "[INFO] AWS credentials expired or missing. Initiating MFA session..."
		MFA_SERIAL=$$(aws iam list-mfa-devices --query 'MFADevices[0].SerialNumber' --output text 2>/dev/null)
		if [ -z "$$MFA_SERIAL" ] || [ "$$MFA_SERIAL" = "None" ]; then
			echo "[ERROR] No MFA device found for current IAM user."; exit 1
		fi
		echo "[INFO] MFA device: $$MFA_SERIAL"
		printf "Enter MFA token code: "; read MFA_CODE
		STS=$$(aws sts get-session-token --serial-number $$MFA_SERIAL --token-code $$MFA_CODE --duration-seconds 43200 2>&1)
		if [ $$? -ne 0 ]; then echo "[ERROR] $$STS"; exit 1; fi
		export AWS_ACCESS_KEY_ID=$$(echo "$$STS" | python3 -c "import sys,json; print(json.load(sys.stdin)['Credentials']['AccessKeyId'])")
		export AWS_SECRET_ACCESS_KEY=$$(echo "$$STS" | python3 -c "import sys,json; print(json.load(sys.stdin)['Credentials']['SecretAccessKey'])")
		export AWS_SESSION_TOKEN=$$(echo "$$STS" | python3 -c "import sys,json; print(json.load(sys.stdin)['Credentials']['SessionToken'])")
		echo "[SUCCESS] MFA session established (valid 12h)."
	else
		echo "[INFO] AWS credentials valid."
	fi
	echo "→ Creating ECR repository..."
	aws ecr describe-repositories --repository-names $(ORCHESTRATOR) --region $(AWS_REGION) 2>/dev/null || \
		aws ecr create-repository --repository-name $(ORCHESTRATOR) --region $(AWS_REGION)
	echo "→ Creating IAM policy..."
	aws iam create-policy \
		--policy-name orchestrator-policy \
		--policy-document file://$(AWS_DIR)/iam-policy.json 2>/dev/null || echo "  policy already exists, skipping"
	echo "→ Creating dev IAM role..."
	aws iam create-role \
		--role-name orchestrator-dev-role \
		--assume-role-policy-document file://$(AWS_DIR)/trust-policy-dev.json 2>/dev/null || echo "  dev role already exists, skipping"
	aws iam attach-role-policy \
		--role-name orchestrator-dev-role \
		--policy-arn arn:aws:iam::$(AWS_ACCOUNT):policy/orchestrator-policy
	echo "→ Creating prod IAM role..."
	aws iam create-role \
		--role-name orchestrator-role \
		--assume-role-policy-document file://$(AWS_DIR)/trust-policy-prod.json 2>/dev/null || echo "  prod role already exists, skipping"
	aws iam attach-role-policy \
		--role-name orchestrator-role \
		--policy-arn arn:aws:iam::$(AWS_ACCOUNT):policy/orchestrator-policy
	echo "✅ AWS setup complete"

# ── Orchestrator: deploy ───────────────────────────────────────
orchestrator-build:
	@if [ -z "$(ENV)" ]; then echo "❌ ENV required (dev|prod)"; exit 1; fi
	echo "🔨 Building orchestrator $(GIT_SHA) for $(ENV)..."
	docker buildx build --platform $(PLATFORM) --load \
		-t $(IMAGE):$(ORCHESTRATOR)-$(GIT_SHA) \
		-t $(IMAGE):$(ENV)-latest \
		-f orchestrator/Dockerfile \
		.

orchestrator-push:
	@if [ -z "$(ENV)" ]; then echo "❌ ENV required (dev|prod)"; exit 1; fi
	echo "📤 Pushing orchestrator to ECR..."
	docker push $(IMAGE):$(ORCHESTRATOR)-$(GIT_SHA)
	docker push $(IMAGE):$(ENV)-latest

orchestrator-deploy:
	@if [ -z "$(ENV)" ]; then echo "❌ ENV required (dev|prod)"; exit 1; fi
	if [ "$(ENV)" = "prod" ] && [ "$(GIT_BRANCH)" != "main" ]; then
		echo "❌ Prod deploy requires main branch (current: $(GIT_BRANCH))"; exit 1
	fi
	if ! aws sts get-caller-identity > /dev/null 2>&1; then
		echo "[INFO] AWS credentials expired or missing. Initiating MFA session..."
		MFA_SERIAL=$$(aws iam list-mfa-devices --query 'MFADevices[0].SerialNumber' --output text 2>/dev/null)
		if [ -z "$$MFA_SERIAL" ] || [ "$$MFA_SERIAL" = "None" ]; then
			echo "[ERROR] No MFA device found for current IAM user."; exit 1
		fi
		echo "[INFO] MFA device: $$MFA_SERIAL"
		printf "Enter MFA token code: "; read MFA_CODE
		STS=$$(aws sts get-session-token --serial-number $$MFA_SERIAL --token-code $$MFA_CODE --duration-seconds 43200 2>&1)
		if [ $$? -ne 0 ]; then echo "[ERROR] $$STS"; exit 1; fi
		export AWS_ACCESS_KEY_ID=$$(echo "$$STS" | python3 -c "import sys,json; print(json.load(sys.stdin)['Credentials']['AccessKeyId'])")
		export AWS_SECRET_ACCESS_KEY=$$(echo "$$STS" | python3 -c "import sys,json; print(json.load(sys.stdin)['Credentials']['SecretAccessKey'])")
		export AWS_SESSION_TOKEN=$$(echo "$$STS" | python3 -c "import sys,json; print(json.load(sys.stdin)['Credentials']['SessionToken'])")
		echo "[SUCCESS] MFA session established (valid 12h)."
	else
		echo "[INFO] AWS credentials valid."
	fi
	aws ecr get-login-password --region $(AWS_REGION) | \
		docker login --username AWS --password-stdin $(AWS_ACCOUNT).dkr.ecr.$(AWS_REGION).amazonaws.com
	echo "🔨 Building orchestrator $(GIT_SHA) for $(ENV)..."
	docker buildx build --platform $(PLATFORM) --load \
		-t $(IMAGE):$(ORCHESTRATOR)-$(GIT_SHA) \
		-t $(IMAGE):$(ENV)-latest \
		-f orchestrator/Dockerfile \
		.
	echo "📤 Pushing to ECR..."
	docker push $(IMAGE):$(ORCHESTRATOR)-$(GIT_SHA)
	docker push $(IMAGE):$(ENV)-latest
	echo "🚀 Applying k8s manifests..."
	kubectl apply -k $(K8S_DIR)/overlays/$(ENV) --server-side=true --force-conflicts=true --context=$(KUBE_CONTEXT)
	kubectl rollout status deployment/$(ORCHESTRATOR) -n services --context=$(KUBE_CONTEXT) --timeout=5m
	echo "✅ Deployed orchestrator to $(ENV)"

orchestrator-deploy-only:
	@if [ -z "$(ENV)" ]; then echo "❌ ENV required (dev|prod)"; exit 1; fi
	echo "🚀 Applying k8s manifests to $(ENV)..."
	kubectl apply -k $(K8S_DIR)/overlays/$(ENV) --server-side=true --force-conflicts=true --context=$(KUBE_CONTEXT)
	kubectl rollout status deployment/$(ORCHESTRATOR) -n services --context=$(KUBE_CONTEXT) --timeout=5m

orchestrator-preview:
	@if [ -z "$(ENV)" ]; then echo "❌ ENV required (dev|prod)"; exit 1; fi
	kubectl kustomize $(K8S_DIR)/overlays/$(ENV)

orchestrator-rollback:
	@if [ -z "$(ENV)" ]; then echo "❌ ENV required (dev|prod)"; exit 1; fi
	kubectl rollout undo deployment/$(ORCHESTRATOR) -n services --context=$(KUBE_CONTEXT)

orchestrator-status:
	@if [ -z "$(ENV)" ]; then echo "❌ ENV required (dev|prod)"; exit 1; fi
	kubectl get deployment $(ORCHESTRATOR) -n services --context=$(KUBE_CONTEXT)
	echo ""
	kubectl get pods -n services -l app=$(ORCHESTRATOR) --context=$(KUBE_CONTEXT)
