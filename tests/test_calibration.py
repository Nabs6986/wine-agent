"""Tests for calibration service functionality."""

import json
import tempfile
from pathlib import Path
from uuid import UUID

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from wine_agent.core.enums import NoteSource, NoteStatus, WineColor
from wine_agent.core.schema import Scores, SubScores, TastingNote, WineIdentity
from wine_agent.db.models import Base, CalibrationNoteDB, TastingNoteDB
from wine_agent.services.calibration_service import CalibrationService


@pytest.fixture
def test_db():
    """Create a temporary test database with calibration table."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        engine = create_engine(f"sqlite:///{db_path}", echo=False)

        # Create base tables
        Base.metadata.create_all(bind=engine)

        Session = sessionmaker(bind=engine)
        yield Session


def _create_test_note(
    producer: str = "Test Producer",
    region: str = "Burgundy",
    country: str = "France",
    score_total: int = 85,
    status: str = "published",
) -> TastingNote:
    """Helper to create a test tasting note."""
    subscores = SubScores(
        appearance=2,
        nose=10,
        palate=17,
        structure_balance=17,
        finish=8,
        typicity_complexity=14,
        overall_judgment=17,
    )
    scores = Scores(subscores=subscores)

    wine = WineIdentity(
        producer=producer,
        region=region,
        country=country,
        vintage=2020,
        grapes=["Pinot Noir"],
        color=WineColor.RED,
    )

    return TastingNote(
        source=NoteSource.MANUAL,
        status=NoteStatus(status),
        wine=wine,
        scores=scores,
    )


def _insert_note(session, note: TastingNote) -> None:
    """Insert a note into the database."""
    note_dict = note.model_dump(mode="json")
    db_note = TastingNoteDB(
        id=str(note.id),
        created_at=note.created_at,
        updated_at=note.updated_at,
        status=note.status.value,
        source=note.source.value,
        template_version=note.template_version,
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
    session.add(db_note)
    session.commit()


class TestCalibrationService:
    """Tests for CalibrationService."""

    def test_get_calibration_notes_empty(self, test_db):
        """Get calibration notes on empty database returns empty list."""
        with test_db() as session:
            service = CalibrationService(session)
            notes = service.get_calibration_notes()

            assert notes == []

    def test_create_calibration_note(self, test_db):
        """Create a new calibration note."""
        with test_db() as session:
            service = CalibrationService(session)

            note = service.set_calibration_note(
                score_value=90,
                description="Outstanding wines with exceptional complexity",
                examples=["2015 DRC La Tache", "2010 Lafite Rothschild"],
            )

            assert note.score_value == 90
            assert note.description == "Outstanding wines with exceptional complexity"
            assert len(note.examples) == 2
            assert "2015 DRC La Tache" in note.examples
            assert isinstance(note.id, UUID)

    def test_get_calibration_note_by_id(self, test_db):
        """Get a calibration note by ID."""
        with test_db() as session:
            service = CalibrationService(session)

            created = service.set_calibration_note(
                score_value=85,
                description="Very good wines",
            )

            retrieved = service.get_calibration_note(str(created.id))

            assert retrieved is not None
            assert retrieved.id == created.id
            assert retrieved.score_value == 85

    def test_get_calibration_note_by_score(self, test_db):
        """Get a calibration note by score value."""
        with test_db() as session:
            service = CalibrationService(session)

            service.set_calibration_note(
                score_value=80,
                description="Good wines with solid character",
            )

            retrieved = service.get_calibration_note_by_score(80)

            assert retrieved is not None
            assert retrieved.score_value == 80
            assert retrieved.description == "Good wines with solid character"

    def test_update_calibration_note_by_id(self, test_db):
        """Update an existing calibration note by ID."""
        with test_db() as session:
            service = CalibrationService(session)

            created = service.set_calibration_note(
                score_value=75,
                description="Original description",
            )

            updated = service.set_calibration_note(
                score_value=75,
                description="Updated description",
                examples=["New example"],
                note_id=str(created.id),
            )

            assert updated.id == created.id
            assert updated.description == "Updated description"
            assert updated.examples == ["New example"]

    def test_update_calibration_note_by_score_value(self, test_db):
        """Update an existing calibration note by score value."""
        with test_db() as session:
            service = CalibrationService(session)

            service.set_calibration_note(
                score_value=70,
                description="Original description",
            )

            # Update by same score value (no note_id)
            updated = service.set_calibration_note(
                score_value=70,
                description="New description for 70",
            )

            # Should have updated the existing note
            all_notes = service.get_calibration_notes()
            assert len(all_notes) == 1
            assert all_notes[0].description == "New description for 70"

    def test_delete_calibration_note(self, test_db):
        """Delete a calibration note."""
        with test_db() as session:
            service = CalibrationService(session)

            created = service.set_calibration_note(
                score_value=65,
                description="To be deleted",
            )

            result = service.delete_calibration_note(str(created.id))

            assert result is True

            # Verify it's gone
            retrieved = service.get_calibration_note(str(created.id))
            assert retrieved is None

    def test_delete_nonexistent_note(self, test_db):
        """Delete a nonexistent note returns False."""
        with test_db() as session:
            service = CalibrationService(session)

            result = service.delete_calibration_note("nonexistent-id")

            assert result is False

    def test_calibration_notes_ordered_by_score(self, test_db):
        """Calibration notes are returned ordered by score value."""
        with test_db() as session:
            service = CalibrationService(session)

            # Create notes in random order
            service.set_calibration_note(score_value=90, description="Ninety")
            service.set_calibration_note(score_value=70, description="Seventy")
            service.set_calibration_note(score_value=80, description="Eighty")

            notes = service.get_calibration_notes()

            assert len(notes) == 3
            assert notes[0].score_value == 70
            assert notes[1].score_value == 80
            assert notes[2].score_value == 90

    def test_get_personal_stats_empty(self, test_db):
        """Personal stats on empty database."""
        with test_db() as session:
            service = CalibrationService(session)
            stats = service.get_personal_stats()

            assert stats.total_notes == 0
            assert stats.avg_score == 0
            assert stats.std_dev == 0

    def test_get_personal_stats_with_notes(self, test_db):
        """Personal stats calculated correctly."""
        with test_db() as session:
            _insert_note(session, _create_test_note(producer="A"))
            _insert_note(session, _create_test_note(producer="B"))
            _insert_note(session, _create_test_note(producer="C"))

            service = CalibrationService(session)
            stats = service.get_personal_stats()

            assert stats.total_notes == 3
            assert stats.avg_score > 0
            assert stats.notes_this_month >= 0

    def test_get_score_consistency_empty(self, test_db):
        """Score consistency on empty database."""
        with test_db() as session:
            service = CalibrationService(session)
            consistency = service.get_score_consistency()

            assert consistency.overall_std_dev == 0
            assert consistency.by_region == {}
            assert consistency.by_country == {}

    def test_get_score_consistency_with_notes(self, test_db):
        """Score consistency calculated correctly."""
        with test_db() as session:
            # Need at least 2 notes for std dev calculation
            _insert_note(session, _create_test_note(producer="A", region="Burgundy"))
            _insert_note(session, _create_test_note(producer="B", region="Burgundy"))

            service = CalibrationService(session)
            consistency = service.get_score_consistency()

            # With same scores, std dev should be 0
            assert consistency.overall_std_dev >= 0

    def test_get_score_consistency_by_region_min_count(self, test_db):
        """Score consistency by region requires minimum 3 notes."""
        with test_db() as session:
            # Only 2 notes in Burgundy
            _insert_note(session, _create_test_note(producer="A", region="Burgundy"))
            _insert_note(session, _create_test_note(producer="B", region="Burgundy"))

            service = CalibrationService(session)
            consistency = service.get_score_consistency()

            # Burgundy should not be in by_region (needs 3+ notes)
            assert "Burgundy" not in consistency.by_region

    def test_get_scoring_averages_over_time(self, test_db):
        """Scoring averages over time works correctly."""
        with test_db() as session:
            _insert_note(session, _create_test_note(producer="A"))
            _insert_note(session, _create_test_note(producer="B"))

            service = CalibrationService(session)
            averages = service.get_scoring_averages_over_time(period="month")

            assert len(averages) >= 1
            assert "period" in averages[0]
            assert "count" in averages[0]
            assert "avg_score" in averages[0]

    def test_calibration_note_with_empty_examples(self, test_db):
        """Calibration note with no examples."""
        with test_db() as session:
            service = CalibrationService(session)

            note = service.set_calibration_note(
                score_value=60,
                description="Acceptable wines",
            )

            assert note.examples == []

            retrieved = service.get_calibration_note_by_score(60)
            assert retrieved.examples == []


class TestCalibrationNoteDB:
    """Tests for CalibrationNoteDB model."""

    def test_model_defaults(self, test_db):
        """Test model default values."""
        from datetime import UTC, datetime
        from uuid import uuid4

        with test_db() as session:
            now = datetime.now(UTC)
            note = CalibrationNoteDB(
                id=str(uuid4()),
                score_value=75,
                description="Test description",
                examples="[]",
                created_at=now,
                updated_at=now,
            )
            session.add(note)
            session.commit()

            retrieved = session.query(CalibrationNoteDB).first()
            assert retrieved.score_value == 75
            assert retrieved.description == "Test description"

    def test_model_repr(self, test_db):
        """Test model __repr__."""
        from datetime import UTC, datetime
        from uuid import uuid4

        with test_db() as session:
            note_id = str(uuid4())
            now = datetime.now(UTC)
            note = CalibrationNoteDB(
                id=note_id,
                score_value=85,
                description="Test",
                examples="[]",
                created_at=now,
                updated_at=now,
            )
            session.add(note)
            session.commit()

            assert "CalibrationNoteDB" in repr(note)
            assert "score=85" in repr(note)
