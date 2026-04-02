"""
HTTP client for the orchestrator control-plane API.

Encapsulates all three calls an agent makes:
  - get_pending_jobs()  — claim jobs to execute
  - report_status()     — push running / success / failed updates
  - heartbeat()         — liveness signal
"""

import logging
import uuid
from datetime import datetime
from typing import Any

import requests
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class JobPayload(BaseModel):
    """Mirrors orchestrator's JobPayload — keep in sync with routes/jobs.py."""

    job_id: uuid.UUID
    pipeline_id: uuid.UUID
    connector: str
    params: dict[str, Any]
    credentials: dict[str, str]
    start_time: datetime | None = None
    end_time: datetime | None = None
    state: dict[str, Any] = {}


class OrchestratorClient:
    def __init__(self, base_url: str, agent_id: uuid.UUID, api_key: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._agent_id = agent_id
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Content-Type": "application/json",
                "X-Agent-Key": api_key,
            }
        )

    def get_pending_jobs(self) -> list[JobPayload]:
        resp = self._session.get(
            f"{self._base_url}/jobs/pending",
            params={"agent_id": str(self._agent_id)},
            timeout=30,
        )
        resp.raise_for_status()
        return [JobPayload(**j) for j in resp.json()]

    def report_status(
        self,
        job_id: uuid.UUID,
        status: str,
        rows_synced: int | None = None,
        error: str | None = None,
        next_state: dict[str, Any] | None = None,
    ) -> None:
        resp = self._session.post(
            f"{self._base_url}/jobs/{job_id}/status",
            json={
                "status": status,
                "rows_synced": rows_synced,
                "error": error,
                "next_state": next_state,
            },
            timeout=10,
        )
        resp.raise_for_status()

    def heartbeat(self) -> None:
        resp = self._session.post(
            f"{self._base_url}/agents/{self._agent_id}/heartbeat",
            timeout=10,
        )
        resp.raise_for_status()
