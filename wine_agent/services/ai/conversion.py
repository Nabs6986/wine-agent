"""Conversion service for AI-assisted tasting note conversion."""

import hashlib
import logging
import os
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from wine_agent.core.enums import NoteSource, NoteStatus
from wine_agent.core.schema import AIConversionRun, InboxItem, TastingNote
from wine_agent.db.repositories import (
    AIConversionRepository,
    InboxRepository,
    TastingNoteRepository,
)
from wine_agent.services.ai.client import AIClient, AIProvider, get_ai_client
from wine_agent.services.ai.prompts import PROMPT_VERSION

logger = logging.getLogger(__name__)


@dataclass
class ConversionResult:
    """Result of a conversion attempt."""

    success: bool
    tasting_note: TastingNote | None = None
    conversion_run: AIConversionRun | None = None
    error_message: str | None = None


class ConversionService:
    """Service for converting inbox items to structured tasting notes."""

    def __init__(
        self,
        session: Session,
        ai_client: AIClient | None = None,
    ):
        """
        Initialize the conversion service.

        Args:
            session: SQLAlchemy database session.
            ai_client: Optional pre-configured AI client. If not provided,
                      will be created from environment variables.
        """
        self.session = session
        self.inbox_repo = InboxRepository(session)
        self.note_repo = TastingNoteRepository(session)
        self.conversion_repo = AIConversionRepository(session)

        if ai_client:
            self._ai_client = ai_client
        else:
            self._ai_client = None

    @property
    def ai_client(self) -> AIClient:
        """Get or create the AI client from environment variables."""
        if self._ai_client is None:
            self._ai_client = self._create_client_from_env()
        return self._ai_client

    def _create_client_from_env(self) -> AIClient:
        """Create an AI client from environment variables."""
        provider = os.environ.get("AI_PROVIDER", "anthropic").lower()
        model = os.environ.get("AI_MODEL")

        if provider == "anthropic":
            api_key = os.environ.get("ANTHROPIC_API_KEY")
            if not api_key:
                raise ValueError(
                    "ANTHROPIC_API_KEY environment variable is required"
                )
        elif provider == "openai":
            api_key = os.environ.get("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEY environment variable is required")
        else:
            raise ValueError(f"Unsupported AI provider: {provider}")

        return get_ai_client(provider=provider, api_key=api_key, model=model)

    def convert_inbox_item(
        self,
        inbox_item_id: UUID | str,
        hints: dict[str, Any] | None = None,
    ) -> ConversionResult:
        """
        Convert an inbox item to a structured tasting note.

        Args:
            inbox_item_id: The UUID of the inbox item to convert.
            hints: Optional hints to guide the AI conversion.

        Returns:
            ConversionResult with the tasting note or error details.
        """
        # Get the inbox item
        inbox_item = self.inbox_repo.get_by_id(inbox_item_id)
        if inbox_item is None:
            return ConversionResult(
                success=False,
                error_message=f"Inbox item {inbox_item_id} not found",
            )

        # Check if already converted
        existing_note = self.note_repo.get_by_inbox_item_id(inbox_item_id)
        if existing_note is not None:
            return ConversionResult(
                success=True,
                tasting_note=existing_note,
                error_message="Item already converted",
            )

        # Generate structured note
        try:
            result = self.ai_client.generate_structured_note(
                raw_text=inbox_item.raw_text,
                hints=hints,
            )
        except Exception as e:
            logger.error(f"AI conversion failed: {e}")
            return ConversionResult(
                success=False,
                error_message=f"AI conversion failed: {str(e)}",
            )

        # Create conversion run record
        input_hash = hashlib.sha256(inbox_item.raw_text.encode()).hexdigest()
        conversion_run = AIConversionRun(
            inbox_item_id=UUID(str(inbox_item_id)) if isinstance(inbox_item_id, str) else inbox_item_id,
            provider=self.ai_client.provider.value,
            model=self.ai_client.model,
            prompt_version=PROMPT_VERSION,
            input_hash=input_hash,
            raw_input=inbox_item.raw_text,
            raw_response=result.raw_response,
            parsed_json=result.parsed_json,
            success=result.success,
            error_message=result.error_message,
            repair_attempts=result.repair_attempts,
        )

        if not result.success:
            # Save failed conversion run for traceability
            self.conversion_repo.create(conversion_run)
            self.session.flush()

            return ConversionResult(
                success=False,
                conversion_run=conversion_run,
                error_message=result.error_message,
            )

        # Create the tasting note
        tasting_note = result.tasting_note
        if tasting_note is None:
            return ConversionResult(
                success=False,
                error_message="AI returned success but no tasting note",
            )

        # Set required fields for the note
        tasting_note.inbox_item_id = UUID(str(inbox_item_id)) if isinstance(inbox_item_id, str) else inbox_item_id
        tasting_note.source = NoteSource.INBOX_CONVERTED
        tasting_note.status = NoteStatus.DRAFT

        # Save the tasting note
        saved_note = self.note_repo.create(tasting_note)

        # Update conversion run with resulting note ID
        conversion_run.resulting_note_id = saved_note.id
        saved_run = self.conversion_repo.create(conversion_run)

        # Mark inbox item as converted
        self.inbox_repo.mark_converted(inbox_item_id, saved_run.id)

        return ConversionResult(
            success=True,
            tasting_note=saved_note,
            conversion_run=saved_run,
        )

    def get_conversion_history(
        self,
        inbox_item_id: UUID | str,
    ) -> list[AIConversionRun]:
        """
        Get the conversion history for an inbox item.

        Args:
            inbox_item_id: The UUID of the inbox item.

        Returns:
            List of AIConversionRun records.
        """
        return self.conversion_repo.get_by_inbox_item_id(inbox_item_id)
