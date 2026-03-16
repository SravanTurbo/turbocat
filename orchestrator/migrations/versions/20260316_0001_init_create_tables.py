"""init: create agents, connections, pipelines, job_runs tables

Revision ID: 0001
Revises:
Create Date: 2026-03-16

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agents",
        sa.Column("agent_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("account_id", UUID(as_uuid=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_agents_account_id", "agents", ["account_id"])

    op.create_table(
        "connections",
        sa.Column("connection_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("account_id", UUID(as_uuid=True), nullable=False),
        sa.Column("source", sa.String(100), nullable=False),
        sa.Column("secret_ref", sa.String(255), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_connections_account_id", "connections", ["account_id"])

    op.create_table(
        "pipelines",
        sa.Column("pipeline_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("account_id", UUID(as_uuid=True), nullable=False),
        sa.Column("agent_id", UUID(as_uuid=True), sa.ForeignKey("agents.agent_id"), nullable=False),
        sa.Column("connection_id", UUID(as_uuid=True), sa.ForeignKey("connections.connection_id"), nullable=False),
        sa.Column("connector", sa.String(100), nullable=False),
        sa.Column("table_name", sa.String(255), nullable=False),
        sa.Column("schedule", sa.String(100), nullable=False),
        sa.Column("params", JSONB, nullable=False, server_default="{}"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_pipelines_account_id", "pipelines", ["account_id"])

    op.create_table(
        "job_runs",
        sa.Column("job_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("pipeline_id", UUID(as_uuid=True), sa.ForeignKey("pipelines.pipeline_id"), nullable=False),
        sa.Column("agent_id", UUID(as_uuid=True), sa.ForeignKey("agents.agent_id"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rows_synced", sa.Integer, nullable=True),
        sa.Column("error", sa.Text, nullable=True),
    )
    op.create_index("ix_job_runs_pipeline_id", "job_runs", ["pipeline_id"])
    op.create_index("ix_job_runs_agent_id", "job_runs", ["agent_id"])


def downgrade() -> None:
    op.drop_table("job_runs")
    op.drop_table("pipelines")
    op.drop_table("connections")
    op.drop_table("agents")
