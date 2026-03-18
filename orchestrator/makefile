.PHONY: setup install install-prod lint format test test-integration migrate migrate-down migration run \
	setup-iam ecr-login build build-local run-docker push deploy deploy-only preview rollback status

ENV ?= local

# ── Config ────────────────────────────────────────────────────
AWS_REGION   ?= ap-south-1
AWS_ACCOUNT  := 767397958941
ORCHESTRATOR := orchestrator
REPO_ROOT    := $(shell git rev-parse --show-toplevel)
IMAGE        := $(AWS_ACCOUNT).dkr.ecr.$(AWS_REGION).amazonaws.com/$(ORCHESTRATOR)
K8S_DIR      := $(CURDIR)/k8s
AWS_DIR      := $(CURDIR)/aws
GIT_SHA      := $(shell git rev-parse --short HEAD 2>/dev/null || echo unknown)
GIT_BRANCH   := $(shell git rev-parse --abbrev-ref HEAD 2>/dev/null || echo unknown)
PLATFORM     ?= linux/amd64
ENV          ?=

KUBE_CONTEXT := $(if $(filter dev,$(ENV)),arn:aws:eks:$(AWS_REGION):$(AWS_ACCOUNT):cluster/development,\
                $(if $(filter prod,$(ENV)),arn:aws:eks:$(AWS_REGION):$(AWS_ACCOUNT):cluster/production,))

# ── Dev ───────────────────────────────────────────────────────
setup:
	poetry config virtualenvs.create true
	poetry install
	poetry run pre-commit install --install-hooks

install:
	poetry install

install-prod:
	poetry install --without dev

lint:
	poetry run flake8 .
	poetry run mypy .

format:
	poetry run black .

test:
	poetry run pytest tests/

test-integration:
	poetry run pytest tests/integration/ -s -v

run:
	APP_ENV=$(ENV) poetry run python -m uvicorn orchestrator.main:app --reload --port 8000

migrate:
	APP_ENV=$(ENV) poetry run alembic upgrade head

migrate-down:
	APP_ENV=$(ENV) poetry run alembic downgrade -1

migration:
	APP_ENV=$(ENV) poetry run alembic revision --autogenerate -m "$(name)"

# ── AWS setup (run once) ──────────────────────────────────────
setup-iam:
	@bash -c '\
		if [ -n "$$AWS_SESSION_TOKEN" ]; then \
			echo "[INFO] MFA session active."; \
		else \
			echo "[INFO] Credentials expired — initiating MFA session..."; \
			MFA_SERIAL=$$(aws iam list-mfa-devices --query "MFADevices[0].SerialNumber" --output text); \
			if [ -z "$$MFA_SERIAL" ] || [ "$$MFA_SERIAL" = "None" ]; then echo "[ERROR] No MFA device found."; exit 1; fi; \
			printf "Enter MFA token code: "; read MFA_CODE; \
			STS=$$(aws sts get-session-token --serial-number "$$MFA_SERIAL" --token-code "$$MFA_CODE" --duration-seconds 43200); \
			export AWS_ACCESS_KEY_ID=$$(echo "$$STS" | python3 -c "import sys,json; print(json.load(sys.stdin)[\"Credentials\"][\"AccessKeyId\"])"); \
			export AWS_SECRET_ACCESS_KEY=$$(echo "$$STS" | python3 -c "import sys,json; print(json.load(sys.stdin)[\"Credentials\"][\"SecretAccessKey\"])"); \
			export AWS_SESSION_TOKEN=$$(echo "$$STS" | python3 -c "import sys,json; print(json.load(sys.stdin)[\"Credentials\"][\"SessionToken\"])"); \
			echo "[SUCCESS] MFA session established (valid 12h)."; \
		fi; \
		echo "Creating ECR repository..."; \
		aws ecr describe-repositories --repository-names $(ORCHESTRATOR) --region $(AWS_REGION) 2>/dev/null \
			|| aws ecr create-repository --repository-name $(ORCHESTRATOR) --region $(AWS_REGION); \
		echo "Creating IAM policy..."; \
		aws iam create-policy --policy-name orchestrator-policy \
			--policy-document file://$(AWS_DIR)/iam-policy.json 2>/dev/null || echo "  policy already exists, skipping"; \
		echo "Creating dev IAM role..."; \
		aws iam create-role --role-name orchestrator-dev-role \
			--assume-role-policy-document file://$(AWS_DIR)/trust-policy-dev.json 2>/dev/null || echo "  dev role already exists, skipping"; \
		echo "Updating dev trust policy..."; \
		aws iam update-assume-role-policy --role-name orchestrator-dev-role \
			--policy-document file://$(AWS_DIR)/trust-policy-dev.json; \
		aws iam attach-role-policy --role-name orchestrator-dev-role \
			--policy-arn arn:aws:iam::$(AWS_ACCOUNT):policy/orchestrator-policy; \
		echo "Creating prod IAM role..."; \
		aws iam create-role --role-name orchestrator-role \
			--assume-role-policy-document file://$(AWS_DIR)/trust-policy-prod.json 2>/dev/null || echo "  prod role already exists, skipping"; \
		echo "Updating prod trust policy..."; \
		aws iam update-assume-role-policy --role-name orchestrator-role \
			--policy-document file://$(AWS_DIR)/trust-policy-prod.json; \
		aws iam attach-role-policy --role-name orchestrator-role \
			--policy-arn arn:aws:iam::$(AWS_ACCOUNT):policy/orchestrator-policy; \
		echo "AWS setup complete" \
	'

# ── Deploy ────────────────────────────────────────────────────
ecr-login:
	@bash -c '\
		if [ -n "$$AWS_SESSION_TOKEN" ]; then \
			echo "[INFO] MFA session active."; \
		else \
			echo "[INFO] Credentials expired — initiating MFA session..."; \
			MFA_SERIAL=$$(aws iam list-mfa-devices --query "MFADevices[0].SerialNumber" --output text); \
			if [ -z "$$MFA_SERIAL" ] || [ "$$MFA_SERIAL" = "None" ]; then echo "[ERROR] No MFA device found."; exit 1; fi; \
			printf "Enter MFA token code: "; read MFA_CODE; \
			STS=$$(aws sts get-session-token --serial-number "$$MFA_SERIAL" --token-code "$$MFA_CODE" --duration-seconds 43200); \
			export AWS_ACCESS_KEY_ID=$$(echo "$$STS" | python3 -c "import sys,json; print(json.load(sys.stdin)[\"Credentials\"][\"AccessKeyId\"])"); \
			export AWS_SECRET_ACCESS_KEY=$$(echo "$$STS" | python3 -c "import sys,json; print(json.load(sys.stdin)[\"Credentials\"][\"SecretAccessKey\"])"); \
			export AWS_SESSION_TOKEN=$$(echo "$$STS" | python3 -c "import sys,json; print(json.load(sys.stdin)[\"Credentials\"][\"SessionToken\"])"); \
			echo "[SUCCESS] MFA session established (valid 12h)."; \
		fi; \
		aws ecr get-login-password --region $(AWS_REGION) | \
			docker login --username AWS --password-stdin $(AWS_ACCOUNT).dkr.ecr.$(AWS_REGION).amazonaws.com \
	'

# Build for local testing (native platform, no ECR tag)
build-local:
	docker buildx build --load \
		-t $(ORCHESTRATOR):local \
		-f $(CURDIR)/Dockerfile \
		$(REPO_ROOT)

# Run the locally built image — requires src/orchestrator/.env.local to exist
run-docker: build-local
	docker run --rm \
		--env-file $(CURDIR)/src/orchestrator/.env.local \
		-p 8000:8000 \
		$(ORCHESTRATOR):local

build:
	@[ -n "$(ENV)" ] || { echo "ENV required (dev|prod)"; exit 1; }
	docker buildx build --platform $(PLATFORM) --load \
		-t $(IMAGE):$(ORCHESTRATOR)-$(GIT_SHA) \
		-t $(IMAGE):$(ENV)-latest \
		-f $(CURDIR)/Dockerfile \
		$(REPO_ROOT)

push:
	@[ -n "$(ENV)" ] || { echo "ENV required (dev|prod)"; exit 1; }
	docker push $(IMAGE):$(ORCHESTRATOR)-$(GIT_SHA)
	docker push $(IMAGE):$(ENV)-latest

deploy:
	@[ -n "$(ENV)" ] || { echo "ENV required (dev|prod)"; exit 1; }
	@bash -c '\
		[ "$(ENV)" != "prod" ] || [ "$(GIT_BRANCH)" = "main" ] || { echo "Prod deploy requires main branch"; exit 1; }; \
		if [ -n "$$AWS_SESSION_TOKEN" ]; then \
			echo "[INFO] MFA session active."; \
		else \
			echo "[INFO] Credentials expired — initiating MFA session..."; \
			MFA_SERIAL=$$(aws iam list-mfa-devices --query "MFADevices[0].SerialNumber" --output text); \
			if [ -z "$$MFA_SERIAL" ] || [ "$$MFA_SERIAL" = "None" ]; then echo "[ERROR] No MFA device found."; exit 1; fi; \
			printf "Enter MFA token code: "; read MFA_CODE; \
			STS=$$(aws sts get-session-token --serial-number "$$MFA_SERIAL" --token-code "$$MFA_CODE" --duration-seconds 43200); \
			export AWS_ACCESS_KEY_ID=$$(echo "$$STS" | python3 -c "import sys,json; print(json.load(sys.stdin)[\"Credentials\"][\"AccessKeyId\"])"); \
			export AWS_SECRET_ACCESS_KEY=$$(echo "$$STS" | python3 -c "import sys,json; print(json.load(sys.stdin)[\"Credentials\"][\"SecretAccessKey\"])"); \
			export AWS_SESSION_TOKEN=$$(echo "$$STS" | python3 -c "import sys,json; print(json.load(sys.stdin)[\"Credentials\"][\"SessionToken\"])"); \
			echo "[SUCCESS] MFA session established (valid 12h)."; \
		fi; \
		aws ecr get-login-password --region $(AWS_REGION) | \
			docker login --username AWS --password-stdin $(AWS_ACCOUNT).dkr.ecr.$(AWS_REGION).amazonaws.com; \
		docker buildx build --platform $(PLATFORM) --load \
			-t $(IMAGE):$(ORCHESTRATOR)-$(GIT_SHA) \
			-t $(IMAGE):$(ENV)-latest \
			-f $(CURDIR)/Dockerfile $(REPO_ROOT); \
		docker push $(IMAGE):$(ORCHESTRATOR)-$(GIT_SHA); \
		docker push $(IMAGE):$(ENV)-latest; \
		kubectl apply -k $(K8S_DIR)/overlays/$(ENV) --server-side=true --force-conflicts=true --context=$(KUBE_CONTEXT); \
		kubectl rollout restart deployment/$(ORCHESTRATOR) -n services --context=$(KUBE_CONTEXT); \
		kubectl rollout status deployment/$(ORCHESTRATOR) -n services --context=$(KUBE_CONTEXT) --timeout=5m \
	'

deploy-only:
	@[ -n "$(ENV)" ] || { echo "ENV required (dev|prod)"; exit 1; }
	kubectl apply -k $(K8S_DIR)/overlays/$(ENV) --server-side=true --force-conflicts=true --context=$(KUBE_CONTEXT)
	kubectl rollout status deployment/$(ORCHESTRATOR) -n services --context=$(KUBE_CONTEXT) --timeout=5m

preview:
	@[ -n "$(ENV)" ] || { echo "ENV required (dev|prod)"; exit 1; }
	kubectl kustomize $(K8S_DIR)/overlays/$(ENV)

rollback:
	@[ -n "$(ENV)" ] || { echo "ENV required (dev|prod)"; exit 1; }
	kubectl rollout undo deployment/$(ORCHESTRATOR) -n services --context=$(KUBE_CONTEXT)

status:
	@[ -n "$(ENV)" ] || { echo "ENV required (dev|prod)"; exit 1; }
	kubectl get deployment $(ORCHESTRATOR) -n services --context=$(KUBE_CONTEXT)
	kubectl get pods -n services -l app=$(ORCHESTRATOR) --context=$(KUBE_CONTEXT)
