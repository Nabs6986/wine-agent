"""Initial schema for Wine Agent.

Revision ID: 0001
Revises:
Create Date: 2025-01-21

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create inbox_items table
    op.create_table(
        "inbox_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("converted", sa.Boolean(), default=False),
        sa.Column("conversion_run_id", sa.String(36), nullable=True),
        sa.Column("tags_json", sa.Text(), default="[]"),
    )

    # Create tasting_notes table
    op.create_table(
        "tasting_notes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(20), default="draft"),
        sa.Column("source", sa.String(20), default="manual"),
        sa.Column("template_version", sa.String(10), default="1.0"),
        sa.Column("inbox_item_id", sa.String(36), nullable=True),
        # Key indexed fields
        sa.Column("producer", sa.String(255), default=""),
        sa.Column("cuvee", sa.String(255), default=""),
        sa.Column("vintage", sa.Integer(), nullable=True),
        sa.Column("country", sa.String(100), default=""),
        sa.Column("region", sa.String(100), default=""),
        sa.Column("grapes_json", sa.Text(), default="[]"),
        sa.Column("color", sa.String(20), nullable=True),
        sa.Column("score_total", sa.Integer(), default=0),
        sa.Column("quality_band", sa.String(20), nullable=True),
        sa.Column("tags_json", sa.Text(), default="[]"),
        # Full note payload
        sa.Column("note_json", sa.Text(), nullable=False),
    )
    op.create_index("ix_tasting_notes_inbox_item_id", "tasting_notes", ["inbox_item_id"])
    op.create_index("ix_tasting_notes_producer", "tasting_notes", ["producer"])
    op.create_index("ix_tasting_notes_vintage", "tasting_notes", ["vintage"])
    op.create_index("ix_tasting_notes_country", "tasting_notes", ["country"])
    op.create_index("ix_tasting_notes_region", "tasting_notes", ["region"])
    op.create_index("ix_tasting_notes_score_total", "tasting_notes", ["score_total"])

    # Create ai_conversion_runs table
    op.create_table(
        "ai_conversion_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("inbox_item_id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("prompt_version", sa.String(20), nullable=False),
        sa.Column("input_hash", sa.String(64), nullable=False),
        sa.Column("raw_input", sa.Text(), nullable=False),
        sa.Column("raw_response", sa.Text(), nullable=False),
        sa.Column("parsed_json", sa.Text(), nullable=True),
        sa.Column("success", sa.Boolean(), default=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("repair_attempts", sa.Integer(), default=0),
        sa.Column("resulting_note_id", sa.String(36), nullable=True),
    )
    op.create_index("ix_ai_conversion_runs_inbox_item_id", "ai_conversion_runs", ["inbox_item_id"])

    # Create revisions table
    op.create_table(
        "revisions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tasting_note_id", sa.String(36), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("changed_fields_json", sa.Text(), default="[]"),
        sa.Column("previous_snapshot", sa.Text(), nullable=False),
        sa.Column("new_snapshot", sa.Text(), nullable=False),
        sa.Column("change_reason", sa.Text(), default=""),
    )
    op.create_index("ix_revisions_tasting_note_id", "revisions", ["tasting_note_id"])


def downgrade() -> None:
    op.drop_index("ix_revisions_tasting_note_id", table_name="revisions")
    op.drop_table("revisions")

    op.drop_index("ix_ai_conversion_runs_inbox_item_id", table_name="ai_conversion_runs")
    op.drop_table("ai_conversion_runs")

    op.drop_index("ix_tasting_notes_score_total", table_name="tasting_notes")
    op.drop_index("ix_tasting_notes_region", table_name="tasting_notes")
    op.drop_index("ix_tasting_notes_country", table_name="tasting_notes")
    op.drop_index("ix_tasting_notes_vintage", table_name="tasting_notes")
    op.drop_index("ix_tasting_notes_producer", table_name="tasting_notes")
    op.drop_index("ix_tasting_notes_inbox_item_id", table_name="tasting_notes")
    op.drop_table("tasting_notes")

    op.drop_table("inbox_items")
