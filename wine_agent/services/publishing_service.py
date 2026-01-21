"""Publishing service for tasting notes."""

import logging
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from wine_agent.core.enums import NoteStatus
from wine_agent.core.schema import Revision, TastingNote
from wine_agent.db.repositories import RevisionRepository, TastingNoteRepository

logger = logging.getLogger(__name__)


@dataclass
class PublishResult:
    """Result of a publish operation."""

    success: bool
    note: TastingNote | None = None
    revision: Revision | None = None
    error_message: str | None = None


class PublishingService:
    """Service for publishing and managing tasting note lifecycle."""

    def __init__(self, session: Session):
        """
        Initialize the publishing service.

        Args:
            session: SQLAlchemy database session.
        """
        self.session = session
        self.note_repo = TastingNoteRepository(session)
        self.revision_repo = RevisionRepository(session)

    def publish_note(self, note_id: UUID | str) -> PublishResult:
        """
        Publish a draft tasting note.

        Creates a revision snapshot and marks the note as published.

        Args:
            note_id: The UUID of the note to publish.

        Returns:
            PublishResult with the published note and revision.
        """
        note = self.note_repo.get_by_id(note_id)

        if note is None:
            return PublishResult(
                success=False,
                error_message=f"Note {note_id} not found",
            )

        if note.status == NoteStatus.PUBLISHED:
            return PublishResult(
                success=False,
                error_message="Note is already published",
            )

        # Validate minimum required fields for publishing
        validation_error = self._validate_for_publish(note)
        if validation_error:
            return PublishResult(
                success=False,
                error_message=validation_error,
            )

        # Get current revision number
        current_revision = self.revision_repo.get_latest_revision_number(note_id)
        new_revision_number = current_revision + 1

        # Create revision snapshot (empty previous for first publish)
        previous_snapshot = {} if current_revision == 0 else note.model_dump(mode="json")
        new_snapshot = note.model_dump(mode="json")

        revision = Revision(
            tasting_note_id=UUID(str(note_id)) if isinstance(note_id, str) else note_id,
            revision_number=new_revision_number,
            changed_fields=["status"],
            previous_snapshot=previous_snapshot,
            new_snapshot=new_snapshot,
            change_reason="Initial publication",
        )

        # Update note status
        note.status = NoteStatus.PUBLISHED

        # Save changes
        try:
            updated_note = self.note_repo.update(note)
            saved_revision = self.revision_repo.create(revision)
            self.session.flush()

            logger.info(f"Published note {note_id} with revision {new_revision_number}")

            return PublishResult(
                success=True,
                note=updated_note,
                revision=saved_revision,
            )
        except Exception as e:
            logger.error(f"Failed to publish note {note_id}: {e}")
            return PublishResult(
                success=False,
                error_message=f"Failed to publish: {str(e)}",
            )

    def save_draft(
        self,
        note_id: UUID | str,
        updates: dict,
    ) -> PublishResult:
        """
        Save updates to a draft note.

        Args:
            note_id: The UUID of the note to update.
            updates: Dictionary of field updates.

        Returns:
            PublishResult with the updated note.
        """
        note = self.note_repo.get_by_id(note_id)

        if note is None:
            return PublishResult(
                success=False,
                error_message=f"Note {note_id} not found",
            )

        if note.status == NoteStatus.PUBLISHED:
            return PublishResult(
                success=False,
                error_message="Cannot edit published notes directly. Create a new revision instead.",
            )

        # Apply updates to the note
        try:
            updated_note = self._apply_updates(note, updates)
            saved_note = self.note_repo.update(updated_note)
            self.session.flush()

            logger.info(f"Saved draft {note_id}")

            return PublishResult(
                success=True,
                note=saved_note,
            )
        except Exception as e:
            logger.error(f"Failed to save draft {note_id}: {e}")
            return PublishResult(
                success=False,
                error_message=f"Failed to save: {str(e)}",
            )

    def get_revisions(self, note_id: UUID | str) -> list[Revision]:
        """
        Get all revisions for a note.

        Args:
            note_id: The UUID of the note.

        Returns:
            List of Revision objects ordered by revision number.
        """
        return self.revision_repo.get_by_note_id(note_id)

    def delete_note(self, note_id: UUID | str) -> PublishResult:
        """
        Delete a draft note.

        Published notes cannot be deleted.

        Args:
            note_id: The UUID of the note to delete.

        Returns:
            PublishResult indicating success or failure.
        """
        note = self.note_repo.get_by_id(note_id)

        if note is None:
            return PublishResult(
                success=False,
                error_message=f"Note {note_id} not found",
            )

        if note.status == NoteStatus.PUBLISHED:
            return PublishResult(
                success=False,
                error_message="Cannot delete published notes",
            )

        try:
            self.note_repo.delete(note_id)
            self.session.flush()

            logger.info(f"Deleted draft {note_id}")

            return PublishResult(success=True)
        except Exception as e:
            logger.error(f"Failed to delete note {note_id}: {e}")
            return PublishResult(
                success=False,
                error_message=f"Failed to delete: {str(e)}",
            )

    def _validate_for_publish(self, note: TastingNote) -> str | None:
        """
        Validate that a note has minimum required fields for publishing.

        Args:
            note: The note to validate.

        Returns:
            Error message if validation fails, None if valid.
        """
        # Require at least producer or vintage to be set
        if not note.wine.producer and not note.wine.vintage:
            return "At least producer or vintage must be set before publishing"

        return None

    def _apply_updates(self, note: TastingNote, updates: dict) -> TastingNote:
        """
        Apply updates dictionary to a note.

        Args:
            note: The note to update.
            updates: Dictionary of updates.

        Returns:
            Updated TastingNote.
        """
        # Handle wine identity updates
        if "wine" in updates:
            wine_updates = updates["wine"]
            for key, value in wine_updates.items():
                if hasattr(note.wine, key):
                    setattr(note.wine, key, value)

        # Handle context updates
        if "context" in updates:
            context_updates = updates["context"]
            for key, value in context_updates.items():
                if hasattr(note.context, key):
                    setattr(note.context, key, value)

        # Handle scores updates
        if "scores" in updates:
            scores_updates = updates["scores"]
            if "subscores" in scores_updates:
                for key, value in scores_updates["subscores"].items():
                    if hasattr(note.scores.subscores, key):
                        setattr(note.scores.subscores, key, value)
            # Recalculate total and quality band
            from wine_agent.core.scoring import calculate_total_score, determine_quality_band
            note.scores.total = calculate_total_score(note.scores.subscores)
            note.scores.quality_band = determine_quality_band(note.scores.total)

        # Handle structure levels updates
        if "structure_levels" in updates:
            sl_updates = updates["structure_levels"]
            for key, value in sl_updates.items():
                if hasattr(note.structure_levels, key):
                    setattr(note.structure_levels, key, value)

        # Handle readiness updates
        if "readiness" in updates:
            readiness_updates = updates["readiness"]
            for key, value in readiness_updates.items():
                if hasattr(note.readiness, key):
                    setattr(note.readiness, key, value)

        # Handle top-level note fields
        note_fields = [
            "appearance_notes", "nose_notes", "palate_notes",
            "structure_notes", "finish_notes", "typicity_notes",
            "overall_notes", "conclusion", "tags",
        ]
        for field in note_fields:
            if field in updates:
                setattr(note, field, updates[field])

        return note
