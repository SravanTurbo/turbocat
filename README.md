# turbocat

Open-source data pipeline system built around a universal agent. Pull data from any source, load it into any warehouse, run everything in whatever infrastructure you control.

## The idea

Most pipeline tools make a trade-off you can't get out of: either data flows through the vendor's infrastructure (Fivetran), or the scheduler has to live next to the data (Airbyte).

turbocat separates the two. The **orchestrator** is a lightweight scheduler and config store — it can run anywhere. The **agent** is the execution unit — it also runs anywhere, polls the orchestrator for work, and writes data to whatever destination you configure. The orchestrator never sees the data.

The agent resolves its destination entirely from its own environment config. That destination can be local (same infra as the agent) for data residency requirements, or remote (a cloud warehouse, a central database) when you want a self-hosted extractor without routing data through a vendor. You decide where the agent runs and where it writes.

This means the agent is a first-class deployable primitive.

## Deployment topologies

**Self-hosted** — Run both the orchestrator and agent inside your own infrastructure. `docker compose up` and everything stays local. Equivalent to how you'd run Airbyte, without requiring the orchestrator to be co-located with the data.

```
[Your Infrastructure]
  Orchestrator  ── schedules jobs, holds pipeline config
  Agent         ── polls orchestrator, runs connectors, writes to warehouse
  Warehouse     ── ClickHouse, Postgres, etc.
```

**Central orchestrator, distributed agents** — Run one orchestrator, deploy agents into multiple remote environments — client accounts, subsidiary regions, isolated cloud accounts, on-prem locations. Each agent writes to a destination in its own environment. Data never leaves that environment. The orchestrator only sees job status, never records.

```
[Your Infrastructure]           [Environment A]
  Orchestrator ──────────────▶  Agent → local warehouse
               ──────────────▶  [Environment B]
                                Agent → local warehouse
```

**Self-hosted extractor** — Run the agent locally or in your own infra, write to a remote cloud warehouse. The orchestrator can live anywhere. This is the Fivetran model but with nothing in between — data goes straight from the agent to your warehouse, with no vendor infrastructure in the path.

```
[Your Infrastructure]           [Cloud Warehouse]
  Orchestrator
  Agent ──────────────────────▶  Snowflake / BigQuery / ClickHouse Cloud
```

In all cases, the agent initiates all communication outbound to the orchestrator — no inbound connections into the agent's network are required.

## Structure

```
turbocat/
├── connectors/   # shared connector library (pip-installable, used by orchestrator + agent)
├── orchestrator/ # control plane — FastAPI + APScheduler + Postgres
└── agent/        # polling worker — runs anywhere, executes connectors, writes to destination
```

## How a sync works

1. APScheduler fires on a cron expression stored per pipeline in Postgres.
2. A `job_run` row is inserted with status `PENDING`.
3. The agent polls `GET /jobs/pending`, claims the row using `SELECT FOR UPDATE SKIP LOCKED` (safe for multiple agent instances), and transitions it to `DISPATCHED`.
4. The executor resolves the connector from the registry, merges pipeline params with credentials, and calls `source.sync(destination)`.
5. The connector streams records from the source API, validates them against a declared schema, batches them, and loads them into the destination.
6. The agent reports `SUCCESS` or `FAILED` back to the orchestrator. On success, the pipeline's state cursor is updated to checkpoint the next incremental sync.

The orchestrator's job ends at step 2. Everything after that happens inside the agent's environment.

## Components

### connectors/

The shared connector library. Pip-installable, imported by both orchestrator and agent.

- `BaseSourceConnector` — abstract base with `extract / get_schema / transform / sync`. Handles batching, validation, and error capture. New connectors implement three methods.
- `BaseDestinationConnector` — abstract base with `load`. ClickHouse is the current destination; the interface is designed to support others.
- Source connectors: Razorpay (orders, customers), Kapture (tickets).
- `RetryableHTTPClient` — shared HTTP client with exponential backoff.
- Connector registry — maps string names (e.g. `"razorpay_orders"`) to connector and config classes, resolved by the agent executor at runtime.

```bash
cd connectors && make setup && make test
```

### orchestrator/

Control plane. Manages pipeline config, schedules, connection credentials, and job dispatch. Has no opinion on where the agent runs or where data is written.

- **Pipeline config** — which connector to run, on what schedule, for which agent, with what params.
- **Connections** — one per source, holding a reference to stored credentials.
- **Job dispatch** — APScheduler triggers `job_run` creation; `GET /jobs/pending` delivers payloads with credentials injected at dispatch time, held in memory only.
- **State management** — incremental sync cursors stored per pipeline, updated only on confirmed success.
- **Agent registry** — heartbeat tracking so you know which agents are alive.

```bash
cd orchestrator && make setup && make migrate && make test
```

### agent/

A Docker container that runs wherever you need data pulled. The orchestrator never needs to know where it is or what it writes to — the agent discovers its destination from its local environment.

Concurrency model:
- `asyncio` event loop drives the poll and heartbeat loops.
- Each job runs in a `ThreadPoolExecutor` thread (connectors are synchronous and I/O-bound).
- A `Semaphore` caps concurrent jobs at `max_workers`.
- Graceful shutdown waits for all in-flight jobs to complete before exiting.

```bash
cd agent && make setup && make lint
```

---

## Why not an existing tool

The core requirement is split execution: scheduling decisions happen in one place, data movement happens in another, and the two are connected only by a poll-based job queue over HTTP.

**Airflow** runs workers in its own environment. Executing work inside a remote network requires a custom operator that dispatches to an external process — you end up rebuilding the agent anyway, plus you inherit Airflow's operational weight.

**Temporal** handles durability and retry better than anything else, but the Temporal server is significant infrastructure and couples every worker to Temporal's SDK. The agent is designed to be a minimal container anyone can run without external dependencies.

**Prefect** is the closest parallel — its work pool + agent pattern is the same model. The trade-off is that connector logic becomes Prefect-idiomatic (decorator-based flows) rather than a standalone reusable library, and Prefect Cloud or a self-hosted server becomes a hard dependency.

**Fivetran** moves data through the vendor's infrastructure. **Managed Airbyte** does the same. Both are non-starters when data residency is a requirement.

turbocat's approach is intentionally minimal: a Postgres-backed job queue, a cron scheduler, and a polling agent. The entire control path is a handful of HTTP endpoints. This is easy to reason about, easy to debug, and deploys into any environment as a single Docker container.
