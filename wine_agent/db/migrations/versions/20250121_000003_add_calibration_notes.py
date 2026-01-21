"""Add calibration notes table.

Revision ID: 0003
Revises: 0002
Create Date: 2025-01-21

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "calibration_notes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("score_value", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("examples", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_calibration_notes_score_value",
        "calibration_notes",
        ["score_value"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_calibration_notes_score_value", table_name="calibration_notes")
    op.drop_table("calibration_notes")
