import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from orchestrator.db import get_db
from orchestrator.models import JobRun, JobStatus, Pipeline
from orchestrator.secrets import get_secret

router = APIRouter()


class JobPayload(BaseModel):
    job_id: uuid.UUID
    pipeline_id: uuid.UUID
    connector: str
    params: dict[str, Any]
    credentials: dict[str, str]


class StatusUpdate(BaseModel):
    status: str  # "running" | "success" | "failed"
    rows_synced: int | None = None
    error: str | None = None


@router.get("/pending", response_model=list[JobPayload])
def get_pending_jobs(agent_id: uuid.UUID, db: Session = Depends(get_db)) -> list[JobPayload]:
    jobs = (
        db.query(JobRun)
        .join(Pipeline, JobRun.pipeline_id == Pipeline.pipeline_id)
        .filter(JobRun.agent_id == agent_id, JobRun.status == JobStatus.PENDING)
        .all()
    )

    payloads = []
    for job in jobs:
        credentials = get_secret(job.pipeline.connection.secret_ref)
        job.status = JobStatus.DISPATCHED
        payloads.append(
            JobPayload(
                job_id=job.job_id,
                pipeline_id=job.pipeline_id,
                connector=job.pipeline.connector,
                params=job.pipeline.params,
                credentials=credentials,
            )
        )

    db.commit()
    return payloads


@router.post("/{job_id}/status")
def update_job_status(job_id: uuid.UUID, body: StatusUpdate, db: Session = Depends(get_db)) -> dict[str, str]:
    job = db.get(JobRun, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    job.status = body.status
    job.rows_synced = body.rows_synced
    job.error = body.error

    now = datetime.now(timezone.utc)
    if body.status == JobStatus.RUNNING and not job.started_at:
        job.started_at = now
    elif body.status in (JobStatus.SUCCESS, JobStatus.FAILED):
        job.completed_at = now

    db.commit()
    return {"status": "ok"}
