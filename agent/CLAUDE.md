# agent

Runs in the client's AWS account as a Docker container. Polls the orchestrator for jobs and executes connectors.

## Source layout

```
src/agent/
├── main.py      # entry point — asyncio loop, signal handlers (SIGTERM/SIGINT), graceful shutdown
├── agent.py     # Agent class — poll loop + heartbeat loop + ThreadPoolExecutor job dispatch
├── executor.py  # run_job() — resolves connector from registry, merges params+credentials, calls source.sync()
├── client.py    # OrchestratorClient — HTTP calls to orchestrator (get_pending_jobs, report_status, heartbeat)
└── settings.py  # Settings(BaseSettings) — ORCHESTRATOR_URL, AGENT_ID, max_workers, poll_interval
```

## Concurrency model

- `asyncio` drives the poll and heartbeat loops.
- Each job runs in a `ThreadPoolExecutor` thread (connectors are synchronous I/O-bound).
- A semaphore caps concurrent jobs at `max_workers`. Poll loop only fetches as many jobs as slots available.
- Graceful shutdown: stop poll loop, wait for all in-flight tasks to finish.

## ClickHouse config

`ClickHouseConfig` is loaded from env vars at startup and passed to the executor. Credentials are never sent to the orchestrator — they come from the client's environment at deploy time.

## Auth

The agent authenticates to the orchestrator using a Bearer JWT. The token is set via the `AGENT_TOKEN` env var and included in all HTTP calls via `client.py`.

## Adding a new connector

Don't add connector code here — add it to the `connectors/` library. The agent resolves connectors by name via the registry (`data_connectors.registry.lookup`).
