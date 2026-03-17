import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload

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
    # Lock matching rows so concurrent agents skip them (no duplicate dispatch)
    jobs = (
        db.query(JobRun)
        .filter(JobRun.agent_id == agent_id, JobRun.status == JobStatus.PENDING)
        .with_for_update(skip_locked=True)
        .all()
    )

    if not jobs:
        return []

    job_ids = [job.job_id for job in jobs]
    for job in jobs:
        job.status = JobStatus.DISPATCHED
    db.commit()  # release locks; jobs are now claimed

    # Reload with relationships to avoid N+1 queries per job
    jobs_with_rels = (
        db.query(JobRun)
        .filter(JobRun.job_id.in_(job_ids))
        .options(joinedload(JobRun.pipeline).joinedload(Pipeline.connection))
        .all()
    )

    return [
        JobPayload(
            job_id=job.job_id,
            pipeline_id=job.pipeline_id,
            connector=job.pipeline.connector,
            params=job.pipeline.params,
            credentials=get_secret(job.pipeline.connection.secret_ref),
        )
        for job in jobs_with_rels
    ]


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
