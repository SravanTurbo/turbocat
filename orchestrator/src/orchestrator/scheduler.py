import uuid
import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from orchestrator.db import get_session_factory
from orchestrator.models import JobRun, JobStatus, Pipeline

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()


def _enqueue_job(pipeline_id: uuid.UUID, agent_id: uuid.UUID) -> None:
    """Insert a pending job_run for a pipeline. Called by APScheduler on cron tick."""
    with get_session_factory()() as db:
        job = JobRun(
            pipeline_id=pipeline_id,
            agent_id=agent_id,
            status=JobStatus.PENDING,
        )
        db.add(job)
        db.commit()
        logger.info("Enqueued job %s for pipeline %s", job.job_id, pipeline_id)


def load_schedules() -> None:
    """Read all active pipelines from DB and register a cron job for each."""
    with get_session_factory()() as db:
        pipelines = db.query(Pipeline).filter(Pipeline.is_active.is_(True)).all()

    for pipeline in pipelines:
        job_id = f"pipeline_{pipeline.pipeline_id}"
        if scheduler.get_job(job_id):
            continue  # already registered

        scheduler.add_job(
            _enqueue_job,
            trigger=CronTrigger.from_crontab(pipeline.schedule),
            id=job_id,
            kwargs={"pipeline_id": pipeline.pipeline_id, "agent_id": pipeline.agent_id},
            replace_existing=True,
        )
        logger.info("Scheduled pipeline %s (%s) → cron: %s", pipeline.pipeline_id, pipeline.connector, pipeline.schedule)


def register_pipeline(pipeline: Pipeline) -> None:
    """Add or update a single pipeline's schedule at runtime."""
    scheduler.add_job(
        _enqueue_job,
        trigger=CronTrigger.from_crontab(pipeline.schedule),
        id=f"pipeline_{pipeline.pipeline_id}",
        kwargs={"pipeline_id": pipeline.pipeline_id, "agent_id": pipeline.agent_id},
        replace_existing=True,
    )


def deregister_pipeline(pipeline_id: uuid.UUID) -> None:
    """Remove a pipeline's schedule at runtime."""
    job_id = f"pipeline_{pipeline_id}"
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)
