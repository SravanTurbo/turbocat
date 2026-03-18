"""pipelines: add state column for incremental sync cursor

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-18

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


SCHEMA = "pipeline_schema"


def upgrade() -> None:
    op.add_column("pipelines", sa.Column("state", JSONB, nullable=True), schema=SCHEMA)


def downgrade() -> None:
    op.drop_column("pipelines", "state", schema=SCHEMA)
