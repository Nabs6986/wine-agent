"""Tests for notes workflow and publishing service."""

import tempfile
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from wine_agent.core.enums import NoteStatus, QualityBand, WineColor
from wine_agent.core.schema import (
    Scores,
    SubScores,
    TastingNote,
    WineIdentity,
)
from wine_agent.db.models import Base
from wine_agent.db.repositories import TastingNoteRepository
from wine_agent.services.publishing_service import PublishingService


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


class TestPublishingService:
    """Tests for PublishingService."""

    def test_publish_creates_revision(self, session: Session) -> None:
        """Test that publishing a note creates a revision snapshot."""
        note_repo = TastingNoteRepository(session)
        service = PublishingService(session)

        # Create a draft note
        note = TastingNote(
            wine=WineIdentity(
                producer="Test Winery",
                cuvee="Reserve",
                vintage=2020,
            ),
            status=NoteStatus.DRAFT,
        )
        note_repo.create(note)
        session.commit()

        # Publish the note
        result = service.publish_note(note.id)
        session.commit()

        assert result.success is True
        assert result.note is not None
        assert result.note.status == NoteStatus.PUBLISHED
        assert result.revision is not None
        assert result.revision.revision_number == 1
        assert result.revision.change_reason == "Initial publication"

    def test_publish_requires_producer_or_vintage(self, session: Session) -> None:
        """Test that publishing requires at least producer or vintage."""
        note_repo = TastingNoteRepository(session)
        service = PublishingService(session)

        # Create a note without producer or vintage
        note = TastingNote(
            wine=WineIdentity(),
            status=NoteStatus.DRAFT,
        )
        note_repo.create(note)
        session.commit()

        # Attempt to publish
        result = service.publish_note(note.id)

        assert result.success is False
        assert "producer or vintage" in result.error_message.lower()

    def test_cannot_publish_already_published_note(self, session: Session) -> None:
        """Test that already published notes cannot be re-published."""
        note_repo = TastingNoteRepository(session)
        service = PublishingService(session)

        # Create and publish a note
        note = TastingNote(
            wine=WineIdentity(producer="Test Winery"),
            status=NoteStatus.DRAFT,
        )
        note_repo.create(note)
        session.commit()

        # First publish
        service.publish_note(note.id)
        session.commit()

        # Attempt second publish
        result = service.publish_note(note.id)

        assert result.success is False
        assert "already published" in result.error_message.lower()

    def test_publish_nonexistent_note(self, session: Session) -> None:
        """Test publishing a nonexistent note returns error."""
        service = PublishingService(session)

        from uuid import uuid4
        result = service.publish_note(uuid4())

        assert result.success is False
        assert "not found" in result.error_message.lower()


class TestSaveDraft:
    """Tests for save_draft functionality."""

    def test_save_draft_updates_wine_identity(self, session: Session) -> None:
        """Test that save_draft updates wine identity fields."""
        note_repo = TastingNoteRepository(session)
        service = PublishingService(session)

        # Create a draft note
        note = TastingNote(
            wine=WineIdentity(producer="Original Producer"),
            status=NoteStatus.DRAFT,
        )
        note_repo.create(note)
        session.commit()

        # Update via save_draft
        result = service.save_draft(note.id, {
            "wine": {
                "producer": "Updated Producer",
                "cuvee": "New Cuvee",
                "vintage": 2019,
            }
        })
        session.commit()

        assert result.success is True
        assert result.note.wine.producer == "Updated Producer"
        assert result.note.wine.cuvee == "New Cuvee"
        assert result.note.wine.vintage == 2019

    def test_save_draft_recalculates_scores(self, session: Session) -> None:
        """Test that saving draft recalculates total score from subscores."""
        note_repo = TastingNoteRepository(session)
        service = PublishingService(session)

        # Create a draft note with initial scores
        note = TastingNote(
            wine=WineIdentity(producer="Test"),
            scores=Scores(
                subscores=SubScores(
                    appearance=1,
                    nose=5,
                    palate=10,
                    structure_balance=10,
                    finish=5,
                    typicity_complexity=8,
                    overall_judgment=10,
                )
            ),
            status=NoteStatus.DRAFT,
        )
        note_repo.create(note)
        session.commit()

        # Update scores via save_draft
        result = service.save_draft(note.id, {
            "scores": {
                "subscores": {
                    "appearance": 2,
                    "nose": 12,
                    "palate": 20,
                    "structure_balance": 20,
                    "finish": 10,
                    "typicity_complexity": 16,
                    "overall_judgment": 20,
                }
            }
        })
        session.commit()

        assert result.success is True
        assert result.note.scores.total == 100  # Perfect score
        assert result.note.scores.quality_band == QualityBand.OUTSTANDING

    def test_save_draft_validates_subscores(self, session: Session) -> None:
        """Test that subscores are validated within their ranges."""
        note_repo = TastingNoteRepository(session)
        service = PublishingService(session)

        # Create a draft note
        note = TastingNote(
            wine=WineIdentity(producer="Test"),
            status=NoteStatus.DRAFT,
        )
        note_repo.create(note)
        session.commit()

        # Try to save with valid subscores
        result = service.save_draft(note.id, {
            "scores": {
                "subscores": {
                    "appearance": 2,  # max is 2
                    "nose": 12,  # max is 12
                    "palate": 20,  # max is 20
                    "structure_balance": 20,  # max is 20
                    "finish": 10,  # max is 10
                    "typicity_complexity": 16,  # max is 16
                    "overall_judgment": 20,  # max is 20
                }
            }
        })
        session.commit()

        assert result.success is True
        assert result.note.scores.subscores.appearance == 2
        assert result.note.scores.subscores.nose == 12

    def test_cannot_save_published_note(self, session: Session) -> None:
        """Test that published notes cannot be edited via save_draft."""
        note_repo = TastingNoteRepository(session)
        service = PublishingService(session)

        # Create and publish a note
        note = TastingNote(
            wine=WineIdentity(producer="Test Winery"),
            status=NoteStatus.DRAFT,
        )
        note_repo.create(note)
        session.commit()

        service.publish_note(note.id)
        session.commit()

        # Attempt to save draft
        result = service.save_draft(note.id, {
            "wine": {"producer": "New Name"}
        })

        assert result.success is False
        assert "published" in result.error_message.lower()


class TestDeleteNote:
    """Tests for delete functionality."""

    def test_delete_draft_note(self, session: Session) -> None:
        """Test that draft notes can be deleted."""
        note_repo = TastingNoteRepository(session)
        service = PublishingService(session)

        # Create a draft note
        note = TastingNote(
            wine=WineIdentity(producer="Test"),
            status=NoteStatus.DRAFT,
        )
        note_repo.create(note)
        session.commit()

        note_id = note.id

        # Delete the note
        result = service.delete_note(note_id)
        session.commit()

        assert result.success is True
        assert note_repo.get_by_id(note_id) is None

    def test_cannot_delete_published_note(self, session: Session) -> None:
        """Test that published notes cannot be deleted."""
        note_repo = TastingNoteRepository(session)
        service = PublishingService(session)

        # Create and publish a note
        note = TastingNote(
            wine=WineIdentity(producer="Test Winery"),
            status=NoteStatus.DRAFT,
        )
        note_repo.create(note)
        session.commit()

        service.publish_note(note.id)
        session.commit()

        # Attempt to delete
        result = service.delete_note(note.id)

        assert result.success is False
        assert "published" in result.error_message.lower()


class TestRevisions:
    """Tests for revision functionality."""

    def test_get_revisions_for_note(self, session: Session) -> None:
        """Test retrieving revisions for a published note."""
        note_repo = TastingNoteRepository(session)
        service = PublishingService(session)

        # Create and publish a note
        note = TastingNote(
            wine=WineIdentity(producer="Test Winery"),
            status=NoteStatus.DRAFT,
        )
        note_repo.create(note)
        session.commit()

        service.publish_note(note.id)
        session.commit()

        # Get revisions
        revisions = service.get_revisions(note.id)

        assert len(revisions) == 1
        assert revisions[0].revision_number == 1

    def test_revision_contains_snapshot(self, session: Session) -> None:
        """Test that revision contains the note snapshot data."""
        note_repo = TastingNoteRepository(session)
        service = PublishingService(session)

        # Create a note with specific data
        note = TastingNote(
            wine=WineIdentity(
                producer="Snapshot Test Winery",
                cuvee="Test Reserve",
                vintage=2018,
                color=WineColor.RED,
            ),
            overall_notes="This is a test note for snapshot verification",
            status=NoteStatus.DRAFT,
        )
        note_repo.create(note)
        session.commit()

        # Publish
        result = service.publish_note(note.id)
        session.commit()

        # Check snapshot
        snapshot = result.revision.new_snapshot

        assert snapshot["wine"]["producer"] == "Snapshot Test Winery"
        assert snapshot["wine"]["cuvee"] == "Test Reserve"
        assert snapshot["wine"]["vintage"] == 2018
        assert snapshot["overall_notes"] == "This is a test note for snapshot verification"


class TestScoreCalculation:
    """Tests for score calculation persistence."""

    def test_score_total_calculated_correctly(self, session: Session) -> None:
        """Test that total score is calculated from subscores."""
        note_repo = TastingNoteRepository(session)

        note = TastingNote(
            wine=WineIdentity(producer="Score Test"),
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

        note_repo.create(note)
        session.commit()

        # Total should be 2+10+18+17+9+14+18 = 88
        retrieved = note_repo.get_by_id(note.id)
        assert retrieved.scores.total == 88
        assert retrieved.scores.quality_band == QualityBand.GOOD

    def test_quality_bands(self, session: Session) -> None:
        """Test that quality bands are assigned correctly."""
        note_repo = TastingNoteRepository(session)

        # Test cases: score -> expected band
        test_cases = [
            (60, QualityBand.POOR),
            (75, QualityBand.ACCEPTABLE),
            (85, QualityBand.GOOD),
            (92, QualityBand.VERY_GOOD),
            (97, QualityBand.OUTSTANDING),
        ]

        for total_target, expected_band in test_cases:
            # Calculate subscores to hit target (distribute evenly-ish)
            # Max possible: 2+12+20+20+10+16+20 = 100
            note = TastingNote(
                wine=WineIdentity(producer=f"Test {total_target}"),
                scores=Scores(
                    subscores=SubScores(
                        appearance=min(2, total_target),
                        nose=min(12, max(0, (total_target - 2) * 12 // 98)),
                        palate=min(20, max(0, (total_target - 2) * 20 // 98)),
                        structure_balance=min(20, max(0, (total_target - 2) * 20 // 98)),
                        finish=min(10, max(0, (total_target - 2) * 10 // 98)),
                        typicity_complexity=min(16, max(0, (total_target - 2) * 16 // 98)),
                        overall_judgment=min(20, max(0, (total_target - 2) * 20 // 98)),
                    )
                ),
            )
            note_repo.create(note)

        session.commit()


class TestFullWorkflow:
    """Integration tests for the complete notes workflow."""

    def test_draft_to_publish_workflow(self, session: Session) -> None:
        """Test the complete workflow: create draft -> edit -> publish -> view."""
        note_repo = TastingNoteRepository(session)
        service = PublishingService(session)

        # Step 1: Create draft
        note = TastingNote(
            wine=WineIdentity(
                producer="Workflow Test Winery",
                vintage=2020,
            ),
            status=NoteStatus.DRAFT,
        )
        note_repo.create(note)
        session.commit()

        assert note.status == NoteStatus.DRAFT

        # Step 2: Edit draft
        result = service.save_draft(note.id, {
            "wine": {
                "cuvee": "Grand Reserve",
                "region": "Napa Valley",
                "country": "USA",
            },
            "overall_notes": "Excellent wine with complex flavors",
            "scores": {
                "subscores": {
                    "appearance": 2,
                    "nose": 11,
                    "palate": 18,
                    "structure_balance": 18,
                    "finish": 9,
                    "typicity_complexity": 15,
                    "overall_judgment": 18,
                }
            }
        })
        session.commit()

        assert result.success is True
        assert result.note.wine.cuvee == "Grand Reserve"
        assert result.note.scores.total == 91  # 2+11+18+18+9+15+18

        # Step 3: Publish
        publish_result = service.publish_note(note.id)
        session.commit()

        assert publish_result.success is True
        assert publish_result.note.status == NoteStatus.PUBLISHED

        # Step 4: Verify revision exists
        revisions = service.get_revisions(note.id)
        assert len(revisions) == 1
        assert revisions[0].new_snapshot["wine"]["producer"] == "Workflow Test Winery"
        assert revisions[0].new_snapshot["wine"]["cuvee"] == "Grand Reserve"
        assert revisions[0].new_snapshot["scores"]["total"] == 91

    def test_cannot_edit_after_publish(self, session: Session) -> None:
        """Test that editing is blocked after publishing."""
        note_repo = TastingNoteRepository(session)
        service = PublishingService(session)

        # Create and publish
        note = TastingNote(
            wine=WineIdentity(producer="Test"),
            status=NoteStatus.DRAFT,
        )
        note_repo.create(note)
        session.commit()

        service.publish_note(note.id)
        session.commit()

        # Attempt to edit
        result = service.save_draft(note.id, {
            "wine": {"producer": "Hacked Name"}
        })

        assert result.success is False

        # Verify original data unchanged
        retrieved = note_repo.get_by_id(note.id)
        assert retrieved.wine.producer == "Test"
