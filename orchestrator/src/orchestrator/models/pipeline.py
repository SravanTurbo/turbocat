import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from orchestrator.models.base import Base

if TYPE_CHECKING:
    from orchestrator.models.agent import Agent
    from orchestrator.models.connection import Connection
    from orchestrator.models.job_run import JobRun


class Pipeline(Base):
    __tablename__ = "pipelines"

    pipeline_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    account_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    agent_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agents.agent_id"), nullable=False)
    connection_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("connections.connection_id"), nullable=False)
    connector: Mapped[str] = mapped_column(String(100), nullable=False)  # e.g. "razorpay_orders"
    table_name: Mapped[str] = mapped_column(String(255), nullable=False)  # source table being synced
    schedule: Mapped[str] = mapped_column(String(100), nullable=False)  # cron expression
    params: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    agent: Mapped["Agent"] = relationship("Agent")
    connection: Mapped["Connection"] = relationship("Connection", back_populates="pipelines")
    job_runs: Mapped[list["JobRun"]] = relationship("JobRun", back_populates="pipeline")
