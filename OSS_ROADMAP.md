# Open-Source Readiness Roadmap

This document tracks what needs to change to make turbocat fully self-sufficient for local or cloud-agnostic deployment.

## Phase Overview

| Phase | Description | Depends on | Status |
|-------|-------------|-----------|--------|
| 1 | Local dev stack (Docker) | — | TODO |
| 2 | Credential store portability | Phase 1 | TODO |
| 3 | APScheduler durability | Phase 1 | TODO |
| 4 | Client UI | — | TODO |
| 5 | CI/CD + contributor docs | — | TODO |

---

## Phase 1 — Local Dev Stack

**Goal:** `docker compose up` starts the full stack.

- Create `agent/Dockerfile`
- Create root `docker-compose.yml` (postgres, orchestrator, agent, optional clickhouse)
- Create `.env.local.example`
- Add `make dev-up / dev-down / dev-logs` to root Makefile

---

## Phase 2 — Credential Store Portability

**Goal:** No AWS account required to run the system.

- Currently: connector credentials stored in AWS Secrets Manager
- Add `CREDENTIAL_BACKEND=postgres` (default) backed by Postgres with Fernet encryption
- Keep AWS Secrets Manager as optional alternative (`CREDENTIAL_BACKEND=aws`)
- New Alembic migration for credential storage

---

## Phase 3 — APScheduler Durability

**Goal:** Pipeline schedules survive orchestrator restarts.

- Currently: APScheduler uses an in-memory jobstore (schedules lost on restart)
- Switch to `SQLAlchemyJobStore` backed by Postgres
- On startup: replay active pipelines from DB into scheduler

---

## Phase 4 — Client UI

**Goal:** Web UI for managing connections, pipelines, and monitoring sync runs (like Fivetran).

- New `client/` directory — Next.js + TypeScript + Tailwind + shadcn/ui
- Pages: Connections, Pipelines, Run history, Agents
- All backed by existing orchestrator REST API

---

## Phase 5 — CI/CD + Contributor Docs

**Goal:** PRs tested automatically; easy to add new connectors.

- GitHub Actions CI (lint, typecheck, test for all components)
- Remove hardcoded internal AWS account ID / region from k8s manifests and Makefile
- `connectors/CONTRIBUTING.md` — how to scaffold and register a new source connector

---

See `.context/oss-roadmap.md` for full implementation detail on each phase.
