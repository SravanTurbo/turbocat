"""
Worker function — runs a single connector sync job.

Designed to execute inside a ThreadPoolExecutor thread.
Credentials are passed as function arguments and remain in local scope
for the lifetime of this call — they are never written to disk or stored
on any shared object.
"""

import logging
from typing import Any

from data_connectors.destinations.clickhouse.config import ClickHouseConfig
from data_connectors.destinations.clickhouse.connector import ClickHouseDestination
from data_connectors.registry import lookup

from agent.client import JobPayload, OrchestratorClient

logger = logging.getLogger(__name__)


def run_job(
    job: JobPayload, ch_config: ClickHouseConfig, client: OrchestratorClient
) -> None:
    """
    Execute one sync job end-to-end and report status back to the orchestrator.

    Steps:
      1. Report RUNNING so the orchestrator knows this job has been picked up.
      2. Build source connector with credentials from the job payload.
      3. Build ClickHouse destination from agent-local config.
      4. Run source.sync() — extract → validate → batch → load.
      5. Report SUCCESS (with next_state cursor) or FAILED (with error message).

    Status reporting failures are logged but never re-raised — a transient
    network error should not crash the worker or prevent the sync from running.
    """
    logger.info("Job %s starting (connector=%s)", job.job_id, job.connector)

    try:
        client.report_status(job.job_id, "running")
    except Exception as exc:
        logger.warning("Could not report RUNNING for job %s: %s", job.job_id, exc)

    try:
        connector_cls, config_cls = lookup(job.connector)
        # Merge params first, credentials second so credentials always win on conflict.
        # Config classes use extra="ignore" so pipeline-level keys (e.g. lookback_days)
        # are silently dropped.
        merged: dict[str, Any] = {**job.params, **job.credentials}
        source = connector_cls(config_cls(**merged))
        destination = ClickHouseDestination(ch_config)
        result = source.sync(
            destination,
            start_time=job.start_time,
            end_time=job.end_time,
            state=job.state or None,
        )
    except Exception as exc:
        logger.exception("Job %s failed with unhandled exception", job.job_id)
        _safe_report(client, job, "failed", error=str(exc))
        return

    if result.status == "success":
        logger.info("Job %s succeeded — %s", job.job_id, result.summary())
        _safe_report(
            client,
            job,
            "success",
            rows_synced=result.records_loaded,
            next_state=result.next_state or None,
        )
    else:
        logger.error("Job %s failed — %s", job.job_id, result.error)
        _safe_report(
            client,
            job,
            "failed",
            rows_synced=result.records_loaded,
            error=result.error,
        )


def _safe_report(
    client: OrchestratorClient,
    job: JobPayload,
    status: str,
    rows_synced: int | None = None,
    error: str | None = None,
    next_state: dict | None = None,  # type: ignore[type-arg]
) -> None:
    try:
        client.report_status(
            job.job_id,
            status,
            rows_synced=rows_synced,
            error=error,
            next_state=next_state,
        )
    except Exception as exc:
        logger.warning(
            "Could not report %s for job %s: %s", status.upper(), job.job_id, exc
        )
