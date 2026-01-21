"""SQLAlchemy ORM models for Wine Agent database."""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _utc_now() -> datetime:
    """Return current UTC datetime (timezone-aware)."""
    return datetime.now(UTC)


def _generate_uuid() -> str:
    """Generate a UUID string."""
    return str(uuid4())


class Base(DeclarativeBase):
    """Base class for all ORM models."""

    pass


class InboxItemDB(Base):
    """
    Database model for inbox items.

    Stores raw, unstructured tasting notes before AI conversion.
    """

    __tablename__ = "inbox_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_generate_uuid)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now, onupdate=_utc_now)
    converted: Mapped[bool] = mapped_column(Boolean, default=False)
    conversion_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    tags_json: Mapped[str] = mapped_column(Text, default="[]")  # JSON array

    def __repr__(self) -> str:
        preview = self.raw_text[:50] + "..." if len(self.raw_text) > 50 else self.raw_text
        return f"<InboxItemDB(id={self.id}, preview='{preview}')>"


class TastingNoteDB(Base):
    """
    Database model for tasting notes.

    Stores structured wine tasting notes with key fields as columns
    for indexing, and the full note payload as JSON.
    """

    __tablename__ = "tasting_notes"

    # Primary key
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_generate_uuid)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now, onupdate=_utc_now)

    # Status and source
    status: Mapped[str] = mapped_column(String(20), default="draft")  # draft/published
    source: Mapped[str] = mapped_column(String(20), default="manual")  # manual/inbox-converted/imported
    template_version: Mapped[str] = mapped_column(String(10), default="1.0")

    # Link to inbox item (if converted from inbox)
    inbox_item_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)

    # Key indexed fields for search/filtering
    producer: Mapped[str] = mapped_column(String(255), default="", index=True)
    cuvee: Mapped[str] = mapped_column(String(255), default="")
    vintage: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    country: Mapped[str] = mapped_column(String(100), default="", index=True)
    region: Mapped[str] = mapped_column(String(100), default="", index=True)
    grapes_json: Mapped[str] = mapped_column(Text, default="[]")  # JSON array
    color: Mapped[str | None] = mapped_column(String(20), nullable=True)
    score_total: Mapped[int] = mapped_column(Integer, default=0, index=True)
    quality_band: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Tags for filtering
    tags_json: Mapped[str] = mapped_column(Text, default="[]")  # JSON array

    # Full structured payload as JSON
    note_json: Mapped[str] = mapped_column(Text, nullable=False)

    # Optional links to canonical entities (added in Phase 1 for catalog integration)
    vintage_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    wine_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)

    def __repr__(self) -> str:
        return f"<TastingNoteDB(id={self.id}, producer='{self.producer}', vintage={self.vintage})>"


class AIConversionRunDB(Base):
    """
    Database model for AI conversion runs.

    Stores traceability information for AI-assisted conversions.
    """

    __tablename__ = "ai_conversion_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_generate_uuid)
    inbox_item_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)

    # AI provider info
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(20), nullable=False)

    # Input/output
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_input: Mapped[str] = mapped_column(Text, nullable=False)
    raw_response: Mapped[str] = mapped_column(Text, nullable=False)
    parsed_json: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON string

    # Result status
    success: Mapped[bool] = mapped_column(Boolean, default=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    repair_attempts: Mapped[int] = mapped_column(Integer, default=0)

    # Link to resulting note
    resulting_note_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    def __repr__(self) -> str:
        return f"<AIConversionRunDB(id={self.id}, provider='{self.provider}', success={self.success})>"


class RevisionDB(Base):
    """
    Database model for tasting note revisions.

    Tracks changes made to published notes for audit purposes.
    """

    __tablename__ = "revisions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_generate_uuid)
    tasting_note_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)

    # Change tracking
    changed_fields_json: Mapped[str] = mapped_column(Text, default="[]")  # JSON array
    previous_snapshot: Mapped[str] = mapped_column(Text, nullable=False)  # JSON
    new_snapshot: Mapped[str] = mapped_column(Text, nullable=False)  # JSON
    change_reason: Mapped[str] = mapped_column(Text, default="")

    def __repr__(self) -> str:
        return f"<RevisionDB(id={self.id}, note_id={self.tasting_note_id}, rev={self.revision_number})>"


class CalibrationNoteDB(Base):
    """
    Database model for calibration notes.

    Stores user-defined descriptions of what each score level means
    for personal reference during wine scoring.
    """

    __tablename__ = "calibration_notes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_generate_uuid)
    score_value: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    examples: Mapped[str] = mapped_column(Text, default="[]")  # JSON array of wine names
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now, onupdate=_utc_now)

    def __repr__(self) -> str:
        return f"<CalibrationNoteDB(id={self.id}, score={self.score_value})>"
