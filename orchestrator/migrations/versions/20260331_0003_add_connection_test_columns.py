"""add last_tested_at to connections

Revision ID: 0003
Revises: 0002
Create Date: 2026-03-31

status already exists (values: active | failed); we extend its meaning to
include 'untested' for connections that have been saved but never tested.
last_tested_at records when the most recent test ran.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "pipeline_schema"


def upgrade() -> None:
    op.add_column(
        "connections",
        sa.Column("last_tested_at", sa.DateTime(timezone=True), nullable=True),
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_column("connections", "last_tested_at", schema=SCHEMA)
