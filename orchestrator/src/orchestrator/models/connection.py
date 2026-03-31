from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from orchestrator.models.base import Base

if TYPE_CHECKING:
    from orchestrator.models.pipeline import Pipeline


class ConnectionStatus(str, enum.Enum):
    UNTESTED = "untested"  # saved but never tested
    ACTIVE = "active"  # last test passed
    FAILED = "failed"  # last test failed


class Connection(Base):
    __tablename__ = "connections"

    connection_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    account_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    secret_ref: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=ConnectionStatus.UNTESTED)
    last_tested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    pipelines: Mapped[list[Pipeline]] = relationship("Pipeline", back_populates="connection")
