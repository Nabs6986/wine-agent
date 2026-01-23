"""Add entitlement system tables.

Revision ID: 0005
Revises: 0004
Create Date: 2025-01-23

This migration adds:
- app_configuration: Singleton table for subscription tier and license key storage
- migration_log: Audit table for tracking data migrations
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create app_configuration table (singleton - only one row with id=1)
    op.create_table(
        "app_configuration",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("license_key", sa.String(255), nullable=True),
        sa.Column("license_validated_at", sa.DateTime(), nullable=True),
        sa.Column("subscription_tier", sa.String(20), nullable=False, server_default="free"),
        sa.Column("tier_expires_at", sa.DateTime(), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("machine_id", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        # SQLite doesn't support CHECK constraints directly, so we enforce id=1 in application code
    )

    # Create migration_log table for auditing data migrations
    op.create_table(
        "migration_log",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("migration_name", sa.String(100), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("details_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("error_message", sa.Text(), nullable=True),
    )
    op.create_index("ix_migration_log_migration_name", "migration_log", ["migration_name"])
    op.create_index("ix_migration_log_status", "migration_log", ["status"])
    op.create_index("ix_migration_log_started_at", "migration_log", ["started_at"])

    # Insert default FREE tier configuration
    op.execute(
        """
        INSERT INTO app_configuration (id, subscription_tier, created_at, updated_at)
        VALUES (1, 'free', datetime('now'), datetime('now'))
        """
    )


def downgrade() -> None:
    op.drop_index("ix_migration_log_started_at", table_name="migration_log")
    op.drop_index("ix_migration_log_status", table_name="migration_log")
    op.drop_index("ix_migration_log_migration_name", table_name="migration_log")
    op.drop_table("migration_log")
    op.drop_table("app_configuration")
