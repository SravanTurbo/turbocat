"""add name to connections

Revision ID: 0004
Revises: 0003
Create Date: 2026-03-31

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "pipeline_schema"


def upgrade() -> None:
    op.add_column(
        "connections",
        sa.Column("name", sa.String(255), nullable=False, server_default=""),
        schema=SCHEMA,
    )
    # Drop the server default after backfilling so new rows must supply a name
    op.alter_column("connections", "name", server_default=None, schema=SCHEMA)


def downgrade() -> None:
    op.drop_column("connections", "name", schema=SCHEMA)
