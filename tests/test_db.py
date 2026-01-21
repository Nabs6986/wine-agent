"""Tests for database persistence layer."""

import json
import tempfile
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from wine_agent.core.enums import NoteSource, NoteStatus, QualityBand, WineColor
from wine_agent.core.schema import (
    AIConversionRun,
    InboxItem,
    Revision,
    Scores,
    SubScores,
    TastingNote,
    WineIdentity,
)
from wine_agent.db.models import Base
from wine_agent.db.repositories import (
    AIConversionRepository,
    InboxRepository,
    RevisionRepository,
    TastingNoteRepository,
)


@pytest.fixture
def temp_db_path():
    """Create a temporary database file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir) / "test.db"


@pytest.fixture
def engine(temp_db_path):
    """Create a test database engine."""
    url = f"sqlite:///{temp_db_path}"
    engine = create_engine(url, echo=False)
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def session(engine):
    """Create a database session for testing."""
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()


class TestInboxRepository:
    """Tests for InboxRepository."""

    def test_create_inbox_item(self, session: Session) -> None:
        """Test creating an inbox item."""
        repo = InboxRepository(session)
        item = InboxItem(raw_text="Great Burgundy wine, 2019 Gevrey-Chambertin")

        created = repo.create(item)
        session.commit()

        assert created.id == item.id
        assert created.raw_text == "Great Burgundy wine, 2019 Gevrey-Chambertin"
        assert created.converted is False
        assert created.tags == []

    def test_get_inbox_item_by_id(self, session: Session) -> None:
        """Test retrieving an inbox item by ID."""
        repo = InboxRepository(session)
        item = InboxItem(raw_text="Test note")
        repo.create(item)
        session.commit()

        retrieved = repo.get_by_id(item.id)

        assert retrieved is not None
        assert retrieved.id == item.id
        assert retrieved.raw_text == "Test note"

    def test_get_nonexistent_inbox_item(self, session: Session) -> None:
        """Test retrieving a nonexistent inbox item."""
        repo = InboxRepository(session)
        result = repo.get_by_id(uuid4())
        assert result is None

    def test_list_inbox_items(self, session: Session) -> None:
        """Test listing all inbox items."""
        repo = InboxRepository(session)
        item1 = InboxItem(raw_text="First note")
        item2 = InboxItem(raw_text="Second note")
        repo.create(item1)
        repo.create(item2)
        session.commit()

        items = repo.list_all()

        assert len(items) == 2

    def test_list_unconverted_inbox_items(self, session: Session) -> None:
        """Test listing only unconverted inbox items."""
        repo = InboxRepository(session)
        item1 = InboxItem(raw_text="Unconverted")
        item2 = InboxItem(raw_text="Converted", converted=True)
        repo.create(item1)
        repo.create(item2)
        session.commit()

        items = repo.list_all(include_converted=False)

        assert len(items) == 1
        assert items[0].raw_text == "Unconverted"

    def test_update_inbox_item(self, session: Session) -> None:
        """Test updating an inbox item."""
        repo = InboxRepository(session)
        item = InboxItem(raw_text="Original text")
        repo.create(item)
        session.commit()

        item.raw_text = "Updated text"
        item.tags = ["burgundy"]
        updated = repo.update(item)
        session.commit()

        assert updated.raw_text == "Updated text"
        assert updated.tags == ["burgundy"]

    def test_delete_inbox_item(self, session: Session) -> None:
        """Test deleting an inbox item."""
        repo = InboxRepository(session)
        item = InboxItem(raw_text="To delete")
        repo.create(item)
        session.commit()

        deleted = repo.delete(item.id)
        session.commit()

        assert deleted is True
        assert repo.get_by_id(item.id) is None

    def test_mark_converted(self, session: Session) -> None:
        """Test marking an inbox item as converted."""
        repo = InboxRepository(session)
        item = InboxItem(raw_text="To convert")
        repo.create(item)
        session.commit()

        conversion_run_id = uuid4()
        updated = repo.mark_converted(item.id, conversion_run_id)
        session.commit()

        assert updated is not None
        assert updated.converted is True
        assert updated.conversion_run_id == conversion_run_id


class TestTastingNoteRepository:
    """Tests for TastingNoteRepository."""

    def test_create_tasting_note(self, session: Session) -> None:
        """Test creating a tasting note."""
        repo = TastingNoteRepository(session)
        note = TastingNote(
            wine=WineIdentity(
                producer="Ridge Vineyards",
                cuvee="Monte Bello",
                vintage=2018,
                country="USA",
                region="California",
                color=WineColor.RED,
            ),
            scores=Scores(
                subscores=SubScores(
                    appearance=2,
                    nose=10,
                    palate=18,
                    structure_balance=17,
                    finish=9,
                    typicity_complexity=14,
                    overall_judgment=18,
                )
            ),
        )

        created = repo.create(note)
        session.commit()

        assert created.id == note.id
        assert created.wine.producer == "Ridge Vineyards"
        assert created.scores.total == 88
        assert created.scores.quality_band == QualityBand.GOOD

    def test_get_tasting_note_by_id(self, session: Session) -> None:
        """Test retrieving a tasting note by ID."""
        repo = TastingNoteRepository(session)
        note = TastingNote(
            wine=WineIdentity(producer="Test Producer", vintage=2020)
        )
        repo.create(note)
        session.commit()

        retrieved = repo.get_by_id(note.id)

        assert retrieved is not None
        assert retrieved.wine.producer == "Test Producer"
        assert retrieved.wine.vintage == 2020

    def test_get_tasting_note_by_inbox_item_id(self, session: Session) -> None:
        """Test retrieving a tasting note by inbox item ID."""
        inbox_repo = InboxRepository(session)
        note_repo = TastingNoteRepository(session)

        inbox_item = InboxItem(raw_text="Test")
        inbox_repo.create(inbox_item)

        note = TastingNote(
            inbox_item_id=inbox_item.id,
            source=NoteSource.INBOX_CONVERTED,
            wine=WineIdentity(producer="Converted Producer"),
        )
        note_repo.create(note)
        session.commit()

        retrieved = note_repo.get_by_inbox_item_id(inbox_item.id)

        assert retrieved is not None
        assert retrieved.inbox_item_id == inbox_item.id
        assert retrieved.source == NoteSource.INBOX_CONVERTED

    def test_list_tasting_notes(self, session: Session) -> None:
        """Test listing all tasting notes."""
        repo = TastingNoteRepository(session)
        note1 = TastingNote(wine=WineIdentity(producer="Producer 1"))
        note2 = TastingNote(wine=WineIdentity(producer="Producer 2"))
        repo.create(note1)
        repo.create(note2)
        session.commit()

        notes = repo.list_all()

        assert len(notes) == 2

    def test_list_tasting_notes_by_status(self, session: Session) -> None:
        """Test listing tasting notes filtered by status."""
        repo = TastingNoteRepository(session)
        draft = TastingNote(status=NoteStatus.DRAFT)
        published = TastingNote(status=NoteStatus.PUBLISHED)
        repo.create(draft)
        repo.create(published)
        session.commit()

        drafts = repo.list_all(status="draft")
        published_notes = repo.list_all(status="published")

        assert len(drafts) == 1
        assert drafts[0].status == NoteStatus.DRAFT
        assert len(published_notes) == 1
        assert published_notes[0].status == NoteStatus.PUBLISHED

    def test_update_tasting_note(self, session: Session) -> None:
        """Test updating a tasting note."""
        repo = TastingNoteRepository(session)
        note = TastingNote(
            wine=WineIdentity(producer="Original"),
            status=NoteStatus.DRAFT,
        )
        repo.create(note)
        session.commit()

        note.wine.producer = "Updated"
        note.status = NoteStatus.PUBLISHED
        updated = repo.update(note)
        session.commit()

        # Re-fetch to verify persistence
        retrieved = repo.get_by_id(note.id)
        assert retrieved is not None
        assert retrieved.wine.producer == "Updated"
        assert retrieved.status == NoteStatus.PUBLISHED

    def test_delete_tasting_note(self, session: Session) -> None:
        """Test deleting a tasting note."""
        repo = TastingNoteRepository(session)
        note = TastingNote()
        repo.create(note)
        session.commit()

        deleted = repo.delete(note.id)
        session.commit()

        assert deleted is True
        assert repo.get_by_id(note.id) is None


class TestAIConversionRepository:
    """Tests for AIConversionRepository."""

    def test_create_conversion_run(self, session: Session) -> None:
        """Test creating an AI conversion run."""
        repo = AIConversionRepository(session)
        inbox_id = uuid4()
        run = AIConversionRun(
            inbox_item_id=inbox_id,
            provider="anthropic",
            model="claude-3-sonnet",
            prompt_version="1.0",
            input_hash="abc123",
            raw_input="Test input",
            raw_response='{"wine": {}}',
            parsed_json={"wine": {}},
            success=True,
        )

        created = repo.create(run)
        session.commit()

        assert created.id == run.id
        assert created.provider == "anthropic"
        assert created.success is True

    def test_get_conversion_run_by_id(self, session: Session) -> None:
        """Test retrieving a conversion run by ID."""
        repo = AIConversionRepository(session)
        inbox_id = uuid4()
        run = AIConversionRun(
            inbox_item_id=inbox_id,
            provider="openai",
            model="gpt-4",
            prompt_version="1.0",
            input_hash="def456",
            raw_input="Input",
            raw_response="Response",
        )
        repo.create(run)
        session.commit()

        retrieved = repo.get_by_id(run.id)

        assert retrieved is not None
        assert retrieved.provider == "openai"

    def test_get_conversion_runs_by_inbox_id(self, session: Session) -> None:
        """Test retrieving conversion runs by inbox item ID."""
        repo = AIConversionRepository(session)
        inbox_id = uuid4()

        run1 = AIConversionRun(
            inbox_item_id=inbox_id,
            provider="anthropic",
            model="claude-3",
            prompt_version="1.0",
            input_hash="hash1",
            raw_input="Input 1",
            raw_response="Response 1",
            success=False,
        )
        run2 = AIConversionRun(
            inbox_item_id=inbox_id,
            provider="anthropic",
            model="claude-3",
            prompt_version="1.0",
            input_hash="hash2",
            raw_input="Input 2",
            raw_response="Response 2",
            success=True,
        )
        repo.create(run1)
        repo.create(run2)
        session.commit()

        runs = repo.get_by_inbox_item_id(inbox_id)

        assert len(runs) == 2

    def test_update_conversion_run(self, session: Session) -> None:
        """Test updating a conversion run."""
        repo = AIConversionRepository(session)
        inbox_id = uuid4()
        run = AIConversionRun(
            inbox_item_id=inbox_id,
            provider="anthropic",
            model="claude-3",
            prompt_version="1.0",
            input_hash="hash",
            raw_input="Input",
            raw_response="Response",
            success=False,
        )
        repo.create(run)
        session.commit()

        run.success = True
        run.resulting_note_id = uuid4()
        updated = repo.update(run)
        session.commit()

        assert updated.success is True
        assert updated.resulting_note_id is not None


class TestRevisionRepository:
    """Tests for RevisionRepository."""

    def test_create_revision(self, session: Session) -> None:
        """Test creating a revision."""
        repo = RevisionRepository(session)
        note_id = uuid4()
        revision = Revision(
            tasting_note_id=note_id,
            revision_number=1,
            changed_fields=["wine.producer"],
            previous_snapshot={"wine": {"producer": "Old"}},
            new_snapshot={"wine": {"producer": "New"}},
            change_reason="Corrected producer name",
        )

        created = repo.create(revision)
        session.commit()

        assert created.id == revision.id
        assert created.revision_number == 1
        assert created.change_reason == "Corrected producer name"

    def test_get_revision_by_id(self, session: Session) -> None:
        """Test retrieving a revision by ID."""
        repo = RevisionRepository(session)
        note_id = uuid4()
        revision = Revision(
            tasting_note_id=note_id,
            revision_number=1,
            previous_snapshot={},
            new_snapshot={},
        )
        repo.create(revision)
        session.commit()

        retrieved = repo.get_by_id(revision.id)

        assert retrieved is not None
        assert retrieved.revision_number == 1

    def test_get_revisions_by_note_id(self, session: Session) -> None:
        """Test retrieving all revisions for a note."""
        repo = RevisionRepository(session)
        note_id = uuid4()

        rev1 = Revision(
            tasting_note_id=note_id,
            revision_number=1,
            previous_snapshot={},
            new_snapshot={"v": 1},
        )
        rev2 = Revision(
            tasting_note_id=note_id,
            revision_number=2,
            previous_snapshot={"v": 1},
            new_snapshot={"v": 2},
        )
        repo.create(rev1)
        repo.create(rev2)
        session.commit()

        revisions = repo.get_by_note_id(note_id)

        assert len(revisions) == 2
        assert revisions[0].revision_number == 1
        assert revisions[1].revision_number == 2

    def test_get_latest_revision_number(self, session: Session) -> None:
        """Test getting the latest revision number."""
        repo = RevisionRepository(session)
        note_id = uuid4()

        # No revisions yet
        assert repo.get_latest_revision_number(note_id) == 0

        rev1 = Revision(
            tasting_note_id=note_id,
            revision_number=1,
            previous_snapshot={},
            new_snapshot={},
        )
        repo.create(rev1)
        session.commit()

        assert repo.get_latest_revision_number(note_id) == 1


class TestFullWorkflow:
    """Integration tests for the full workflow."""

    def test_inbox_to_draft_to_published_workflow(self, session: Session) -> None:
        """Test the complete workflow: inbox item -> draft -> published."""
        inbox_repo = InboxRepository(session)
        note_repo = TastingNoteRepository(session)
        conversion_repo = AIConversionRepository(session)
        revision_repo = RevisionRepository(session)

        # Step 1: Create inbox item
        inbox_item = InboxItem(
            raw_text="Amazing 2018 Burgundy Pinot Noir from Domaine test"
        )
        inbox_repo.create(inbox_item)
        session.commit()

        # Step 2: Simulate AI conversion
        conversion_run = AIConversionRun(
            inbox_item_id=inbox_item.id,
            provider="anthropic",
            model="claude-3-sonnet",
            prompt_version="1.0",
            input_hash="test_hash",
            raw_input=inbox_item.raw_text,
            raw_response='{"wine": {"producer": "Domaine test"}}',
            parsed_json={"wine": {"producer": "Domaine test"}},
            success=True,
        )
        conversion_repo.create(conversion_run)

        # Step 3: Create draft tasting note
        draft_note = TastingNote(
            inbox_item_id=inbox_item.id,
            source=NoteSource.INBOX_CONVERTED,
            status=NoteStatus.DRAFT,
            wine=WineIdentity(
                producer="Domaine test",
                vintage=2018,
                region="Burgundy",
                grapes=["Pinot Noir"],
                color=WineColor.RED,
            ),
            scores=Scores(
                subscores=SubScores(
                    appearance=2,
                    nose=10,
                    palate=17,
                    structure_balance=16,
                    finish=8,
                    typicity_complexity=13,
                    overall_judgment=16,
                )
            ),
        )
        note_repo.create(draft_note)

        # Update conversion run with resulting note
        conversion_run.resulting_note_id = draft_note.id
        conversion_repo.update(conversion_run)

        # Mark inbox item as converted
        inbox_repo.mark_converted(inbox_item.id, conversion_run.id)
        session.commit()

        # Verify draft state
        retrieved_note = note_repo.get_by_id(draft_note.id)
        assert retrieved_note is not None
        assert retrieved_note.status == NoteStatus.DRAFT
        assert retrieved_note.scores.total == 82
        assert retrieved_note.scores.quality_band == QualityBand.GOOD

        # Step 4: Publish the note
        previous_snapshot = retrieved_note.model_dump(mode="json")
        retrieved_note.status = NoteStatus.PUBLISHED
        note_repo.update(retrieved_note)

        # Create revision record
        revision = Revision(
            tasting_note_id=draft_note.id,
            revision_number=1,
            changed_fields=["status"],
            previous_snapshot=previous_snapshot,
            new_snapshot=retrieved_note.model_dump(mode="json"),
            change_reason="Published note",
        )
        revision_repo.create(revision)
        session.commit()

        # Verify published state
        published_note = note_repo.get_by_id(draft_note.id)
        assert published_note is not None
        assert published_note.status == NoteStatus.PUBLISHED

        # Verify revision history
        revisions = revision_repo.get_by_note_id(draft_note.id)
        assert len(revisions) == 1
        assert revisions[0].change_reason == "Published note"

        # Verify inbox item is marked as converted
        converted_inbox = inbox_repo.get_by_id(inbox_item.id)
        assert converted_inbox is not None
        assert converted_inbox.converted is True
