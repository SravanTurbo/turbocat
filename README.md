# data-pipelines

Monorepo for the data pipeline system — connector library, orchestrator, and client agent.

## What This Does

Collects data from external sources (Razorpay, Kapture, Salesforce, Shopify, etc.), loads it into a per-client ClickHouse warehouse, and makes it queryable via CubeJS. Each client gets their own isolated data stack in their own AWS account. Our infrastructure only holds pipeline configuration and schedules — raw data never touches our systems.

## Structure

```
data-pipelines/
├── connectors/     # shared connector library (pip-installable, imported by orchestrator + agent)
├── orchestrator/   # control plane — FastAPI + APScheduler + Postgres + Secrets Manager
└── agent/          # runs in client's AWS account — polls for jobs, executes connectors
```

Infrastructure (deploying the agent, ClickHouse, CubeJS into a client's account, or deploying the orchestrator into ours) lives in the `platform` repo. Deployment targets vary per client — some deployments go into the client's own AWS account, others into our managed infrastructure — so infra is intentionally kept separate from this repo.

## Architecture

```
[Our AWS]
  Orchestrator  ── holds pipeline configs, credentials, and schedules
  Viz Layer     ── dashboards, routes queries to per-client CubeJS endpoint

       ▲ poll / status reports (outbound from client)
       │

[Client AWS Account]
  Agent         ── polls orchestrator for jobs, runs connectors, writes to ClickHouse
  ClickHouse    ── data warehouse (data never leaves this account)
  CubeJS        ── semantic layer and query API
```

Data never leaves the client's AWS account. The agent initiates all communication outbound to our orchestrator — no inbound connections into the client VPC are required.

Credentials (API keys for Razorpay, Kapture, etc.) live in our AWS Secrets Manager. They are fetched by the orchestrator per job, included in the job payload delivered to the agent, and held in memory for the duration of that sync only — never written to disk.

## How a Sync Works

1. APScheduler fires on a cron expression stored per pipeline in Postgres.
2. A `job_run` row is inserted with status `PENDING`.
3. The agent polls `GET /jobs/pending`, claims the row using `SELECT FOR UPDATE SKIP LOCKED` (safe for multiple agent instances), and transitions it to `DISPATCHED`.
4. The executor resolves the connector from the registry, merges pipeline params with credentials, and calls `source.sync(destination)`.
5. The connector streams records from the source API, validates them against a declared schema, batches them, and loads them into ClickHouse.
6. The agent reports `SUCCESS` or `FAILED` back to the orchestrator. On success, the pipeline's state cursor is updated to checkpoint the next incremental sync.

## Components

### connectors/

The shared connector library. Imported by both orchestrator and agent. Contains:

- `BaseSourceConnector` — abstract base with `extract / get_schema / transform / sync`. Handles batching, validation, and error capture. New connectors implement three methods.
- `BaseDestinationConnector` — abstract base with `load`. ClickHouse is the only destination.
- Source connectors: Razorpay (orders, customers), Kapture (tickets).
- `RetryableHTTPClient` — shared HTTP client with exponential backoff.
- Connector registry — maps string names (e.g. `"razorpay_orders"`) to connector and config classes, used by the agent executor at runtime.

```bash
cd connectors && make setup && make test
```

### orchestrator/

Control plane. Manages:

- **Pipeline config** — which connector to run, on what schedule, for which agent, with what params.
- **Connections** — one per source per client, holding a reference to the credentials in Secrets Manager.
- **Job dispatch** — APScheduler triggers `job_run` creation; the `GET /jobs/pending` endpoint delivers payloads with credentials injected at dispatch time.
- **State management** — incremental sync cursors stored per pipeline, updated only on confirmed success.
- **Agent registry** — heartbeat tracking so we know which agents are alive.

```bash
cd orchestrator && make setup && make migrate && make test
```

### agent/

Runs as a Docker container in the client's AWS account. Concurrency model:

- `asyncio` event loop drives the poll and heartbeat loops.
- Each job is dispatched as a `Task` that runs the sync work inside a `ThreadPoolExecutor` thread (connectors are synchronous and I/O-bound).
- A `Semaphore` caps concurrent jobs at `max_workers`. The poll loop only fetches as many jobs as it can immediately start.
- Graceful shutdown waits for all in-flight jobs to complete before exiting.

ClickHouse host, port, and credentials are baked into the agent's environment at deploy time via Terraform. The orchestrator never needs to know where to write — the agent discovers it locally.

```bash
cd agent && make setup && make lint
```

---

## Why We Built This Instead of Using an Existing Tool

The core constraint is data residency: raw data must never leave the client's AWS account, but we need to schedule and monitor syncs centrally. This creates a split-execution requirement — scheduler in our infra, workers in the client's account.

**Airflow** runs workers in its own environment. Getting tasks to execute inside a client's VPC requires a custom operator that dispatches to a remote process, which is effectively rebuilding what we have. You'd also inherit Airflow's operational weight (scheduler, webserver, workers, Celery or Kubernetes executor) without the scheduling UI being worth it at pilot scale.

**Temporal** handles durability and retry better than anything else, but the Temporal server is significant infrastructure. It also couples the client's agent to Temporal's SDK version. The agent needs to be a minimal Docker container that any client can run — not something that requires a Temporal cluster to function.

**Prefect** is the closest parallel. Its work pool + agent pattern is essentially what we built: central scheduler, remote agents polling for work. We would have gained retry logic, backfill, and an observability UI. The trade-off is that our connector logic becomes Prefect-idiomatic (decorator-based flows) rather than a standalone reusable library, and we'd add a Prefect Cloud or self-hosted server dependency. For three pilot clients, the operational overhead outweighs the benefit.

**Fivetran / managed Airbyte** move data through their own infrastructure. Non-starter for data residency.

The architecture here is intentionally minimal: a Postgres-backed job queue, a cron scheduler, and a polling agent. The entire control path is a handful of HTTP endpoints. This is easy to reason about, easy to debug, and deploys into a client account as a single Docker container.

**The right time to reconsider:** When Prefect's retry, backfill, and observability features become more valuable than the operational simplicity of the current approach — roughly at 20+ clients, or when the first client needs an SLA with guaranteed replay. At that point, the connector library remains intact and the executor is the only thing that needs to be re-expressed as Prefect flows.
