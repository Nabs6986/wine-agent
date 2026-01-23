"""Repository classes for database operations."""

import json
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from wine_agent.core.entitlements import AppConfiguration, SubscriptionTier
from wine_agent.core.schema import (
    AIConversionRun,
    InboxItem,
    Revision,
    TastingNote,
)
from wine_agent.db.models import (
    AIConversionRunDB,
    AppConfigurationDB,
    InboxItemDB,
    MigrationLogDB,
    RevisionDB,
    TastingNoteDB,
)


def _utc_now() -> datetime:
    """Return current UTC datetime."""
    return datetime.now(UTC)


class InboxRepository:
    """Repository for InboxItem CRUD operations."""

    def __init__(self, session: Session):
        self.session = session

    def create(self, item: InboxItem) -> InboxItem:
        """
        Create a new inbox item in the database.

        Args:
            item: The InboxItem domain model to create.

        Returns:
            The created InboxItem with updated timestamps.
        """
        db_item = InboxItemDB(
            id=str(item.id),
            raw_text=item.raw_text,
            created_at=item.created_at,
            updated_at=item.updated_at,
            converted=item.converted,
            conversion_run_id=str(item.conversion_run_id) if item.conversion_run_id else None,
            tags_json=json.dumps(item.tags),
        )
        self.session.add(db_item)
        self.session.flush()
        return self._to_domain(db_item)

    def get_by_id(self, item_id: UUID | str) -> InboxItem | None:
        """
        Get an inbox item by ID.

        Args:
            item_id: The UUID of the inbox item.

        Returns:
            The InboxItem if found, None otherwise.
        """
        stmt = select(InboxItemDB).where(InboxItemDB.id == str(item_id))
        db_item = self.session.execute(stmt).scalar_one_or_none()
        return self._to_domain(db_item) if db_item else None

    def list_all(self, include_converted: bool = True) -> list[InboxItem]:
        """
        List all inbox items.

        Args:
            include_converted: If False, exclude converted items.

        Returns:
            List of InboxItem domain models.
        """
        stmt = select(InboxItemDB).order_by(InboxItemDB.created_at.desc())
        if not include_converted:
            stmt = stmt.where(InboxItemDB.converted == False)  # noqa: E712
        result = self.session.execute(stmt).scalars().all()
        return [self._to_domain(item) for item in result]

    def update(self, item: InboxItem) -> InboxItem:
        """
        Update an existing inbox item.

        Args:
            item: The InboxItem with updated values.

        Returns:
            The updated InboxItem.
        """
        stmt = select(InboxItemDB).where(InboxItemDB.id == str(item.id))
        db_item = self.session.execute(stmt).scalar_one_or_none()
        if db_item is None:
            raise ValueError(f"InboxItem with id {item.id} not found")

        db_item.raw_text = item.raw_text
        db_item.updated_at = _utc_now()
        db_item.converted = item.converted
        db_item.conversion_run_id = str(item.conversion_run_id) if item.conversion_run_id else None
        db_item.tags_json = json.dumps(item.tags)

        self.session.flush()
        return self._to_domain(db_item)

    def delete(self, item_id: UUID | str) -> bool:
        """
        Delete an inbox item by ID.

        Args:
            item_id: The UUID of the inbox item to delete.

        Returns:
            True if deleted, False if not found.
        """
        stmt = select(InboxItemDB).where(InboxItemDB.id == str(item_id))
        db_item = self.session.execute(stmt).scalar_one_or_none()
        if db_item is None:
            return False
        self.session.delete(db_item)
        self.session.flush()
        return True

    def mark_converted(self, item_id: UUID | str, conversion_run_id: UUID | str) -> InboxItem | None:
        """
        Mark an inbox item as converted.

        Args:
            item_id: The inbox item ID.
            conversion_run_id: The AI conversion run ID.

        Returns:
            The updated InboxItem, or None if not found.
        """
        stmt = select(InboxItemDB).where(InboxItemDB.id == str(item_id))
        db_item = self.session.execute(stmt).scalar_one_or_none()
        if db_item is None:
            return None

        db_item.converted = True
        db_item.conversion_run_id = str(conversion_run_id)
        db_item.updated_at = _utc_now()
        self.session.flush()
        return self._to_domain(db_item)

    def _to_domain(self, db_item: InboxItemDB) -> InboxItem:
        """Convert DB model to domain model."""
        return InboxItem(
            id=UUID(db_item.id),
            raw_text=db_item.raw_text,
            created_at=db_item.created_at,
            updated_at=db_item.updated_at,
            converted=db_item.converted,
            conversion_run_id=UUID(db_item.conversion_run_id) if db_item.conversion_run_id else None,
            tags=json.loads(db_item.tags_json),
        )


class TastingNoteRepository:
    """Repository for TastingNote CRUD operations."""

    def __init__(self, session: Session):
        self.session = session

    def create(self, note: TastingNote) -> TastingNote:
        """
        Create a new tasting note in the database.

        Args:
            note: The TastingNote domain model to create.

        Returns:
            The created TastingNote.
        """
        note_dict = note.model_dump(mode="json")
        db_note = TastingNoteDB(
            id=str(note.id),
            created_at=note.created_at,
            updated_at=note.updated_at,
            status=note.status.value,
            source=note.source.value,
            template_version=note.template_version,
            inbox_item_id=str(note.inbox_item_id) if note.inbox_item_id else None,
            producer=note.wine.producer,
            cuvee=note.wine.cuvee,
            vintage=note.wine.vintage,
            country=note.wine.country,
            region=note.wine.region,
            grapes_json=json.dumps(note.wine.grapes),
            color=note.wine.color.value if note.wine.color else None,
            score_total=note.scores.total,
            quality_band=note.scores.quality_band.value if note.scores.quality_band else None,
            tags_json=json.dumps(note.tags),
            note_json=json.dumps(note_dict),
        )
        self.session.add(db_note)
        self.session.flush()
        return self._to_domain(db_note)

    def get_by_id(self, note_id: UUID | str) -> TastingNote | None:
        """
        Get a tasting note by ID.

        Args:
            note_id: The UUID of the tasting note.

        Returns:
            The TastingNote if found, None otherwise.
        """
        stmt = select(TastingNoteDB).where(TastingNoteDB.id == str(note_id))
        db_note = self.session.execute(stmt).scalar_one_or_none()
        return self._to_domain(db_note) if db_note else None

    def get_by_inbox_item_id(self, inbox_item_id: UUID | str) -> TastingNote | None:
        """
        Get a tasting note by its associated inbox item ID.

        Args:
            inbox_item_id: The UUID of the inbox item.

        Returns:
            The TastingNote if found, None otherwise.
        """
        stmt = select(TastingNoteDB).where(TastingNoteDB.inbox_item_id == str(inbox_item_id))
        db_note = self.session.execute(stmt).scalar_one_or_none()
        return self._to_domain(db_note) if db_note else None

    def list_all(self, status: str | None = None) -> list[TastingNote]:
        """
        List all tasting notes.

        Args:
            status: Optional filter by status ('draft' or 'published').

        Returns:
            List of TastingNote domain models.
        """
        stmt = select(TastingNoteDB).order_by(TastingNoteDB.created_at.desc())
        if status:
            stmt = stmt.where(TastingNoteDB.status == status)
        result = self.session.execute(stmt).scalars().all()
        return [self._to_domain(note) for note in result]

    def update(self, note: TastingNote) -> TastingNote:
        """
        Update an existing tasting note.

        Args:
            note: The TastingNote with updated values.

        Returns:
            The updated TastingNote.
        """
        stmt = select(TastingNoteDB).where(TastingNoteDB.id == str(note.id))
        db_note = self.session.execute(stmt).scalar_one_or_none()
        if db_note is None:
            raise ValueError(f"TastingNote with id {note.id} not found")

        note_dict = note.model_dump(mode="json")

        db_note.updated_at = _utc_now()
        db_note.status = note.status.value
        db_note.source = note.source.value
        db_note.producer = note.wine.producer
        db_note.cuvee = note.wine.cuvee
        db_note.vintage = note.wine.vintage
        db_note.country = note.wine.country
        db_note.region = note.wine.region
        db_note.grapes_json = json.dumps(note.wine.grapes)
        db_note.color = note.wine.color.value if note.wine.color else None
        db_note.score_total = note.scores.total
        db_note.quality_band = note.scores.quality_band.value if note.scores.quality_band else None
        db_note.tags_json = json.dumps(note.tags)
        db_note.note_json = json.dumps(note_dict)

        self.session.flush()
        return self._to_domain(db_note)

    def delete(self, note_id: UUID | str) -> bool:
        """
        Delete a tasting note by ID.

        Args:
            note_id: The UUID of the tasting note to delete.

        Returns:
            True if deleted, False if not found.
        """
        stmt = select(TastingNoteDB).where(TastingNoteDB.id == str(note_id))
        db_note = self.session.execute(stmt).scalar_one_or_none()
        if db_note is None:
            return False
        self.session.delete(db_note)
        self.session.flush()
        return True

    def _to_domain(self, db_note: TastingNoteDB) -> TastingNote:
        """Convert DB model to domain model."""
        note_data = json.loads(db_note.note_json)
        return TastingNote.model_validate(note_data)


class AIConversionRepository:
    """Repository for AIConversionRun CRUD operations."""

    def __init__(self, session: Session):
        self.session = session

    def create(self, run: AIConversionRun) -> AIConversionRun:
        """
        Create a new AI conversion run record.

        Args:
            run: The AIConversionRun domain model to create.

        Returns:
            The created AIConversionRun.
        """
        db_run = AIConversionRunDB(
            id=str(run.id),
            inbox_item_id=str(run.inbox_item_id),
            created_at=run.created_at,
            provider=run.provider,
            model=run.model,
            prompt_version=run.prompt_version,
            input_hash=run.input_hash,
            raw_input=run.raw_input,
            raw_response=run.raw_response,
            parsed_json=json.dumps(run.parsed_json) if run.parsed_json else None,
            success=run.success,
            error_message=run.error_message,
            repair_attempts=run.repair_attempts,
            resulting_note_id=str(run.resulting_note_id) if run.resulting_note_id else None,
        )
        self.session.add(db_run)
        self.session.flush()
        return self._to_domain(db_run)

    def get_by_id(self, run_id: UUID | str) -> AIConversionRun | None:
        """
        Get an AI conversion run by ID.

        Args:
            run_id: The UUID of the conversion run.

        Returns:
            The AIConversionRun if found, None otherwise.
        """
        stmt = select(AIConversionRunDB).where(AIConversionRunDB.id == str(run_id))
        db_run = self.session.execute(stmt).scalar_one_or_none()
        return self._to_domain(db_run) if db_run else None

    def get_by_inbox_item_id(self, inbox_item_id: UUID | str) -> list[AIConversionRun]:
        """
        Get all conversion runs for an inbox item.

        Args:
            inbox_item_id: The UUID of the inbox item.

        Returns:
            List of AIConversionRun domain models.
        """
        stmt = (
            select(AIConversionRunDB)
            .where(AIConversionRunDB.inbox_item_id == str(inbox_item_id))
            .order_by(AIConversionRunDB.created_at.desc())
        )
        result = self.session.execute(stmt).scalars().all()
        return [self._to_domain(run) for run in result]

    def update(self, run: AIConversionRun) -> AIConversionRun:
        """
        Update an existing AI conversion run.

        Args:
            run: The AIConversionRun with updated values.

        Returns:
            The updated AIConversionRun.
        """
        stmt = select(AIConversionRunDB).where(AIConversionRunDB.id == str(run.id))
        db_run = self.session.execute(stmt).scalar_one_or_none()
        if db_run is None:
            raise ValueError(f"AIConversionRun with id {run.id} not found")

        db_run.success = run.success
        db_run.error_message = run.error_message
        db_run.repair_attempts = run.repair_attempts
        db_run.parsed_json = json.dumps(run.parsed_json) if run.parsed_json else None
        db_run.resulting_note_id = str(run.resulting_note_id) if run.resulting_note_id else None

        self.session.flush()
        return self._to_domain(db_run)

    def _to_domain(self, db_run: AIConversionRunDB) -> AIConversionRun:
        """Convert DB model to domain model."""
        return AIConversionRun(
            id=UUID(db_run.id),
            inbox_item_id=UUID(db_run.inbox_item_id),
            created_at=db_run.created_at,
            provider=db_run.provider,
            model=db_run.model,
            prompt_version=db_run.prompt_version,
            input_hash=db_run.input_hash,
            raw_input=db_run.raw_input,
            raw_response=db_run.raw_response,
            parsed_json=json.loads(db_run.parsed_json) if db_run.parsed_json else None,
            success=db_run.success,
            error_message=db_run.error_message,
            repair_attempts=db_run.repair_attempts,
            resulting_note_id=UUID(db_run.resulting_note_id) if db_run.resulting_note_id else None,
        )


class RevisionRepository:
    """Repository for Revision CRUD operations."""

    def __init__(self, session: Session):
        self.session = session

    def create(self, revision: Revision) -> Revision:
        """
        Create a new revision record.

        Args:
            revision: The Revision domain model to create.

        Returns:
            The created Revision.
        """
        db_revision = RevisionDB(
            id=str(revision.id),
            tasting_note_id=str(revision.tasting_note_id),
            revision_number=revision.revision_number,
            created_at=revision.created_at,
            changed_fields_json=json.dumps(revision.changed_fields),
            previous_snapshot=json.dumps(revision.previous_snapshot),
            new_snapshot=json.dumps(revision.new_snapshot),
            change_reason=revision.change_reason,
        )
        self.session.add(db_revision)
        self.session.flush()
        return self._to_domain(db_revision)

    def get_by_id(self, revision_id: UUID | str) -> Revision | None:
        """
        Get a revision by ID.

        Args:
            revision_id: The UUID of the revision.

        Returns:
            The Revision if found, None otherwise.
        """
        stmt = select(RevisionDB).where(RevisionDB.id == str(revision_id))
        db_revision = self.session.execute(stmt).scalar_one_or_none()
        return self._to_domain(db_revision) if db_revision else None

    def get_by_note_id(self, tasting_note_id: UUID | str) -> list[Revision]:
        """
        Get all revisions for a tasting note.

        Args:
            tasting_note_id: The UUID of the tasting note.

        Returns:
            List of Revision domain models, ordered by revision number.
        """
        stmt = (
            select(RevisionDB)
            .where(RevisionDB.tasting_note_id == str(tasting_note_id))
            .order_by(RevisionDB.revision_number.asc())
        )
        result = self.session.execute(stmt).scalars().all()
        return [self._to_domain(rev) for rev in result]

    def get_latest_revision_number(self, tasting_note_id: UUID | str) -> int:
        """
        Get the latest revision number for a tasting note.

        Args:
            tasting_note_id: The UUID of the tasting note.

        Returns:
            The latest revision number, or 0 if no revisions exist.
        """
        stmt = (
            select(RevisionDB.revision_number)
            .where(RevisionDB.tasting_note_id == str(tasting_note_id))
            .order_by(RevisionDB.revision_number.desc())
            .limit(1)
        )
        result = self.session.execute(stmt).scalar_one_or_none()
        return result if result is not None else 0

    def _to_domain(self, db_revision: RevisionDB) -> Revision:
        """Convert DB model to domain model."""
        return Revision(
            id=UUID(db_revision.id),
            tasting_note_id=UUID(db_revision.tasting_note_id),
            revision_number=db_revision.revision_number,
            created_at=db_revision.created_at,
            changed_fields=json.loads(db_revision.changed_fields_json),
            previous_snapshot=json.loads(db_revision.previous_snapshot),
            new_snapshot=json.loads(db_revision.new_snapshot),
            change_reason=db_revision.change_reason,
        )


class AppConfigRepository:
    """Repository for application configuration (singleton).

    Manages the app configuration which stores subscription tier
    and license information. Only one row exists (id=1).
    """

    def __init__(self, session: Session):
        self.session = session

    def get(self) -> AppConfiguration | None:
        """
        Get the application configuration.

        Returns:
            AppConfiguration if exists, None otherwise.
        """
        stmt = select(AppConfigurationDB).where(AppConfigurationDB.id == 1)
        db_config = self.session.execute(stmt).scalar_one_or_none()
        return self._to_domain(db_config) if db_config else None

    def get_or_create(self) -> AppConfiguration:
        """
        Get the application configuration, creating default if not exists.

        Returns:
            The AppConfiguration (creates with FREE tier defaults if missing).
        """
        config = self.get()
        if config is not None:
            return config

        # Create default configuration
        db_config = AppConfigurationDB(
            id=1,
            subscription_tier="free",
            created_at=_utc_now(),
            updated_at=_utc_now(),
        )
        self.session.add(db_config)
        self.session.flush()
        return self._to_domain(db_config)

    def update_tier(
        self,
        tier: SubscriptionTier,
        expires_at: datetime | None = None,
        license_key: str | None = None,
        email: str | None = None,
    ) -> AppConfiguration:
        """
        Update the subscription tier.

        Args:
            tier: The new subscription tier.
            expires_at: Optional expiration datetime.
            license_key: Optional license key.
            email: Optional email address.

        Returns:
            The updated AppConfiguration.
        """
        stmt = select(AppConfigurationDB).where(AppConfigurationDB.id == 1)
        db_config = self.session.execute(stmt).scalar_one_or_none()

        if db_config is None:
            # Create if not exists
            db_config = AppConfigurationDB(
                id=1,
                subscription_tier=tier.value,
                tier_expires_at=expires_at,
                license_key=license_key,
                email=email,
                created_at=_utc_now(),
                updated_at=_utc_now(),
            )
            self.session.add(db_config)
        else:
            db_config.subscription_tier = tier.value
            db_config.tier_expires_at = expires_at
            db_config.updated_at = _utc_now()
            if license_key is not None:
                db_config.license_key = license_key
                db_config.license_validated_at = _utc_now()
            if email is not None:
                db_config.email = email

        self.session.flush()
        return self._to_domain(db_config)

    def validate_license(self, license_key: str) -> AppConfiguration:
        """
        Mark license as validated.

        Args:
            license_key: The license key that was validated.

        Returns:
            The updated AppConfiguration.
        """
        stmt = select(AppConfigurationDB).where(AppConfigurationDB.id == 1)
        db_config = self.session.execute(stmt).scalar_one_or_none()

        if db_config is None:
            raise ValueError("App configuration not found")

        db_config.license_key = license_key
        db_config.license_validated_at = _utc_now()
        db_config.updated_at = _utc_now()

        self.session.flush()
        return self._to_domain(db_config)

    def _to_domain(self, db_config: AppConfigurationDB) -> AppConfiguration:
        """Convert DB model to domain model."""
        return AppConfiguration(
            license_key=db_config.license_key,
            license_validated_at=db_config.license_validated_at,
            subscription_tier=SubscriptionTier(db_config.subscription_tier),
            tier_expires_at=db_config.tier_expires_at,
            email=db_config.email,
            machine_id=db_config.machine_id,
            created_at=db_config.created_at,
            updated_at=db_config.updated_at,
        )


class MigrationLogRepository:
    """Repository for migration log entries.

    Used to track data migrations for auditing and rollback.
    """

    def __init__(self, session: Session):
        self.session = session

    def create(
        self,
        migration_name: str,
        details: dict | None = None,
    ) -> str:
        """
        Create a new migration log entry.

        Args:
            migration_name: Name of the migration.
            details: Optional details dict.

        Returns:
            The migration log ID.
        """
        db_log = MigrationLogDB(
            migration_name=migration_name,
            started_at=_utc_now(),
            status="pending",
            details_json=json.dumps(details or {}),
        )
        self.session.add(db_log)
        self.session.flush()
        return db_log.id

    def mark_success(self, log_id: str, details: dict | None = None) -> None:
        """
        Mark a migration as successful.

        Args:
            log_id: The migration log ID.
            details: Optional updated details.
        """
        stmt = select(MigrationLogDB).where(MigrationLogDB.id == log_id)
        db_log = self.session.execute(stmt).scalar_one_or_none()
        if db_log is None:
            raise ValueError(f"Migration log {log_id} not found")

        db_log.status = "success"
        db_log.completed_at = _utc_now()
        if details:
            db_log.details_json = json.dumps(details)
        self.session.flush()

    def mark_failed(self, log_id: str, error_message: str) -> None:
        """
        Mark a migration as failed.

        Args:
            log_id: The migration log ID.
            error_message: The error message.
        """
        stmt = select(MigrationLogDB).where(MigrationLogDB.id == log_id)
        db_log = self.session.execute(stmt).scalar_one_or_none()
        if db_log is None:
            raise ValueError(f"Migration log {log_id} not found")

        db_log.status = "failed"
        db_log.completed_at = _utc_now()
        db_log.error_message = error_message
        self.session.flush()

    def get_by_name(self, migration_name: str) -> list[dict]:
        """
        Get all log entries for a migration name.

        Args:
            migration_name: The migration name.

        Returns:
            List of log entry dicts.
        """
        stmt = (
            select(MigrationLogDB)
            .where(MigrationLogDB.migration_name == migration_name)
            .order_by(MigrationLogDB.started_at.desc())
        )
        results = self.session.execute(stmt).scalars().all()
        return [
            {
                "id": r.id,
                "migration_name": r.migration_name,
                "started_at": r.started_at,
                "completed_at": r.completed_at,
                "status": r.status,
                "details": json.loads(r.details_json),
                "error_message": r.error_message,
            }
            for r in results
        ]
