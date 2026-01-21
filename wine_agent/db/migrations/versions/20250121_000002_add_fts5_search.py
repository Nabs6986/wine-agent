"""Add FTS5 full-text search for tasting notes.

Revision ID: 0002
Revises: 0001
Create Date: 2025-01-21

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create FTS5 virtual table for full-text search
    # Using external content mode with manual sync via triggers
    op.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS tasting_notes_fts USING fts5(
            note_id UNINDEXED,
            producer,
            cuvee,
            region,
            country,
            grapes,
            nose_notes,
            palate_notes,
            conclusion,
            tags
        );
    """)

    # Trigger: After INSERT on tasting_notes, insert into FTS
    op.execute("""
        CREATE TRIGGER IF NOT EXISTS tasting_notes_fts_insert
        AFTER INSERT ON tasting_notes
        BEGIN
            INSERT INTO tasting_notes_fts(
                note_id, producer, cuvee, region, country, grapes,
                nose_notes, palate_notes, conclusion, tags
            )
            SELECT
                NEW.id,
                NEW.producer,
                NEW.cuvee,
                NEW.region,
                NEW.country,
                NEW.grapes_json,
                json_extract(NEW.note_json, '$.nose_notes'),
                json_extract(NEW.note_json, '$.palate_notes'),
                json_extract(NEW.note_json, '$.conclusion'),
                NEW.tags_json;
        END;
    """)

    # Trigger: After UPDATE on tasting_notes, update FTS
    op.execute("""
        CREATE TRIGGER IF NOT EXISTS tasting_notes_fts_update
        AFTER UPDATE ON tasting_notes
        BEGIN
            DELETE FROM tasting_notes_fts WHERE note_id = OLD.id;
            INSERT INTO tasting_notes_fts(
                note_id, producer, cuvee, region, country, grapes,
                nose_notes, palate_notes, conclusion, tags
            )
            SELECT
                NEW.id,
                NEW.producer,
                NEW.cuvee,
                NEW.region,
                NEW.country,
                NEW.grapes_json,
                json_extract(NEW.note_json, '$.nose_notes'),
                json_extract(NEW.note_json, '$.palate_notes'),
                json_extract(NEW.note_json, '$.conclusion'),
                NEW.tags_json;
        END;
    """)

    # Trigger: After DELETE on tasting_notes, delete from FTS
    op.execute("""
        CREATE TRIGGER IF NOT EXISTS tasting_notes_fts_delete
        AFTER DELETE ON tasting_notes
        BEGIN
            DELETE FROM tasting_notes_fts WHERE note_id = OLD.id;
        END;
    """)

    # Populate FTS table with existing data
    op.execute("""
        INSERT INTO tasting_notes_fts(
            note_id, producer, cuvee, region, country, grapes,
            nose_notes, palate_notes, conclusion, tags
        )
        SELECT
            id,
            producer,
            cuvee,
            region,
            country,
            grapes_json,
            json_extract(note_json, '$.nose_notes'),
            json_extract(note_json, '$.palate_notes'),
            json_extract(note_json, '$.conclusion'),
            tags_json
        FROM tasting_notes;
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS tasting_notes_fts_delete;")
    op.execute("DROP TRIGGER IF EXISTS tasting_notes_fts_update;")
    op.execute("DROP TRIGGER IF EXISTS tasting_notes_fts_insert;")
    op.execute("DROP TABLE IF EXISTS tasting_notes_fts;")
