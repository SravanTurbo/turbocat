from __future__ import annotations

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from orchestrator.models.base import Base

if TYPE_CHECKING:
    from orchestrator.models.pipeline import Pipeline


class JobStatus(str, enum.Enum):
    PENDING = "pending"
    DISPATCHED = "dispatched"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class JobRun(Base):
    __tablename__ = "job_runs"

    job_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    pipeline_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("pipelines.pipeline_id"), nullable=False, index=True)
    agent_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agents.agent_id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=JobStatus.PENDING)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rows_synced: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    pipeline: Mapped[Pipeline] = relationship("Pipeline", back_populates="job_runs")
