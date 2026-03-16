# data-pipelines

Monorepo for the data pipeline system — connector library, orchestrator, and client agent.

## Structure

```
data-pipelines/
├── connectors/       # Connector library (pip-installable package)
├── orchestrator/     # Control plane — Airflow DAGs + config service API
├── agent/            # L3 agent — runs in client's AWS account
└── infra/            # Terraform — our infra + client account provisioning
```

## How It Fits Together

```
[Our AWS]
  Orchestrator  ──── schedules jobs, holds configs
  Viz Layer     ──── dashboards, routes to per-client CubeJS

[Client AWS account]
  Agent         ──── polls orchestrator, runs connectors locally
  ClickHouse    ──── data warehouse
  CubeJS        ──── semantic layer / query API
```

Data never leaves the client's AWS account. Only job config and status signals cross the boundary.

## Components

### connectors/
The shared connector library. Both orchestrator and agent import this.
See [connectors/README.md](connectors/README.md).

```bash
cd connectors
make setup   # install deps + pre-commit hooks
make test    # run tests
make lint    # flake8 + mypy
```

### orchestrator/
Control plane. Airflow for scheduling, FastAPI for config service API.
_Not yet started._

### agent/
Runs in client's AWS account. Polls orchestrator for jobs, executes connectors locally, writes to client's ClickHouse.
_Not yet started._

### infra/
Terraform modules for:
- `our-infra/` — orchestrator, secrets manager, viz layer
- `client-account/` — agent, ClickHouse, CubeJS deployed into client's AWS account

_Not yet started._
