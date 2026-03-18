.PHONY: connectors-setup connectors-test connectors-lint connectors-format \
	orchestrator-setup-iam orchestrator-ecr-login orchestrator-build orchestrator-push \
	orchestrator-deploy orchestrator-deploy-only orchestrator-preview orchestrator-rollback orchestrator-status \
	orchestrator-migrate orchestrator-test orchestrator-lint

# ── Connectors ────────────────────────────────────────────────
connectors-setup:
	cd connectors && make setup

connectors-test:
	cd connectors && make test

connectors-lint:
	cd connectors && make lint

connectors-format:
	cd connectors && make format

# ── Orchestrator ──────────────────────────────────────────────
orchestrator-setup-iam:
	cd orchestrator && make setup-iam

orchestrator-ecr-login:
	cd orchestrator && make ecr-login

orchestrator-build:
	cd orchestrator && make build ENV=$(ENV)

orchestrator-push:
	cd orchestrator && make push ENV=$(ENV)

orchestrator-deploy:
	cd orchestrator && make deploy ENV=$(ENV)

orchestrator-deploy-only:
	cd orchestrator && make deploy-only ENV=$(ENV)

orchestrator-preview:
	cd orchestrator && make preview ENV=$(ENV)

orchestrator-rollback:
	cd orchestrator && make rollback ENV=$(ENV)

orchestrator-status:
	cd orchestrator && make status ENV=$(ENV)

orchestrator-migrate:
	cd orchestrator && make migrate

orchestrator-test:
	cd orchestrator && make test

orchestrator-lint:
	cd orchestrator && make lint
