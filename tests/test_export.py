"""Tests for export service functionality."""

import json
import tempfile
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from wine_agent.core.enums import (
    DrinkOrHold,
    NoteSource,
    NoteStatus,
    QualityBand,
    StructureLevel,
    WineColor,
)
from wine_agent.core.schema import TastingNote
from wine_agent.db.models import Base, TastingNoteDB
from wine_agent.db.repositories import TastingNoteRepository
from wine_agent.services.export_service import ExportService


@pytest.fixture
def test_db():
    """Create a temporary test database."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        engine = create_engine(f"sqlite:///{db_path}", echo=False)
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine)
        yield Session


def _create_test_note(
    producer: str = "Domaine de la Romanée-Conti",
    cuvee: str = "La Tâche",
    vintage: int = 2018,
    region: str = "Burgundy",
    country: str = "France",
    grapes: list[str] = None,
    status: str = "published",
) -> TastingNote:
    """Helper to create a test tasting note with realistic data."""
    if grapes is None:
        grapes = ["Pinot Noir"]

    note = TastingNote(
        source=NoteSource.MANUAL,
        status=NoteStatus(status),
        nose_notes="Ethereal bouquet of rose petals, wild strawberry, and forest floor.",
        palate_notes="Silky texture with layers of red fruit and subtle spice.",
        conclusion="An exceptional wine showing remarkable purity and elegance.",
    )
    note.wine.producer = producer
    note.wine.cuvee = cuvee
    note.wine.region = region
    note.wine.subregion = "Côte de Nuits"
    note.wine.country = country
    note.wine.vintage = vintage
    note.wine.grapes = grapes
    note.wine.color = WineColor.RED
    note.wine.alcohol_percent = 13.5
    note.wine.appellation = "La Tâche Grand Cru"

    note.scores.subscores.appearance = 2
    note.scores.subscores.nose = 11
    note.scores.subscores.palate = 19
    note.scores.subscores.structure_balance = 19
    note.scores.subscores.finish = 9
    note.scores.subscores.typicity_complexity = 15
    note.scores.subscores.overall_judgment = 19

    note.structure_levels.acidity = StructureLevel.MED_PLUS
    note.structure_levels.tannin = StructureLevel.MEDIUM

    note.readiness.drink_or_hold = DrinkOrHold.HOLD
    note.readiness.window_start_year = 2025
    note.readiness.window_end_year = 2050

    note.tags = ["grand-cru", "burgundy", "cellar-worthy"]

    return note


def _insert_note(session, note: TastingNote) -> TastingNote:
    """Insert a note into the database and return it."""
    repo = TastingNoteRepository(session)
    return repo.create(note)


class TestExportMarkdown:
    """Tests for Markdown export functionality."""

    def test_export_markdown_basic(self, test_db):
        """Export produces valid Markdown with YAML frontmatter."""
        with test_db() as session:
            note = _create_test_note()
            saved_note = _insert_note(session, note)
            session.commit()

            service = ExportService(session)
            markdown = service.export_note_markdown(saved_note.id)

            assert markdown is not None
            assert markdown.startswith("---")
            assert "type: wine_tasting_note" in markdown
            assert "template_version:" in markdown
            assert "---\n\n#" in markdown  # End of frontmatter, start of body

    def test_export_markdown_contains_wine_identity(self, test_db):
        """Export contains wine identity information."""
        with test_db() as session:
            note = _create_test_note(
                producer="Château Margaux",
                cuvee="Grand Vin",
                vintage=2015,
            )
            saved_note = _insert_note(session, note)
            session.commit()

            service = ExportService(session)
            markdown = service.export_note_markdown(saved_note.id)

            assert 'producer: "Château Margaux"' in markdown
            assert 'cuvee: "Grand Vin"' in markdown
            assert "vintage: 2015" in markdown
            assert "# Château Margaux - Grand Vin (2015)" in markdown

    def test_export_markdown_contains_scores(self, test_db):
        """Export contains score information."""
        with test_db() as session:
            note = _create_test_note()
            saved_note = _insert_note(session, note)
            session.commit()

            service = ExportService(session)
            markdown = service.export_note_markdown(saved_note.id)

            # Check YAML frontmatter
            assert "scores:" in markdown
            assert "subscores:" in markdown
            assert "total:" in markdown
            assert "quality_band:" in markdown

            # Check body
            assert "## Quick Snapshot" in markdown
            assert "**Score:**" in markdown
            assert "/ 100" in markdown

    def test_export_markdown_contains_readiness(self, test_db):
        """Export contains readiness information."""
        with test_db() as session:
            note = _create_test_note()
            saved_note = _insert_note(session, note)
            session.commit()

            service = ExportService(session)
            markdown = service.export_note_markdown(saved_note.id)

            assert "readiness:" in markdown
            assert 'drink_or_hold: "hold"' in markdown
            assert "window_start_year: 2025" in markdown
            assert "window_end_year: 2050" in markdown

    def test_export_markdown_contains_sensory_notes(self, test_db):
        """Export contains sensory notes."""
        with test_db() as session:
            note = _create_test_note()
            saved_note = _insert_note(session, note)
            session.commit()

            service = ExportService(session)
            markdown = service.export_note_markdown(saved_note.id)

            assert "## Nose (0-12)" in markdown
            assert "## Palate (0-20)" in markdown
            assert "rose petals" in markdown  # From nose_notes
            assert "Silky texture" in markdown  # From palate_notes

    def test_export_markdown_not_found(self, test_db):
        """Export returns None for non-existent note."""
        with test_db() as session:
            service = ExportService(session)
            markdown = service.export_note_markdown("nonexistent-id")

            assert markdown is None

    def test_export_markdown_contains_tags(self, test_db):
        """Export contains tags."""
        with test_db() as session:
            note = _create_test_note()
            saved_note = _insert_note(session, note)
            session.commit()

            service = ExportService(session)
            markdown = service.export_note_markdown(saved_note.id)

            assert "tags:" in markdown
            assert "- grand-cru" in markdown
            assert "- burgundy" in markdown


class TestExportCSV:
    """Tests for CSV export functionality."""

    def test_export_csv_headers(self, test_db):
        """CSV export has correct headers."""
        with test_db() as session:
            note = _create_test_note()
            _insert_note(session, note)
            session.commit()

            service = ExportService(session)
            csv_content = service.export_notes_csv()

            lines = csv_content.strip().split("\n")
            headers = lines[0].split(",")

            assert "id" in headers
            assert "producer" in headers
            assert "vintage" in headers
            assert "score_total" in headers
            assert "quality_band" in headers
            assert "drink_or_hold" in headers

    def test_export_csv_data(self, test_db):
        """CSV export contains correct data."""
        with test_db() as session:
            note = _create_test_note(
                producer="Test Producer",
                vintage=2020,
            )
            _insert_note(session, note)
            session.commit()

            service = ExportService(session)
            csv_content = service.export_notes_csv()

            assert "Test Producer" in csv_content
            assert "2020" in csv_content
            assert "hold" in csv_content

    def test_export_csv_multiple_notes(self, test_db):
        """CSV export handles multiple notes."""
        with test_db() as session:
            _insert_note(session, _create_test_note(producer="Producer A", vintage=2018))
            _insert_note(session, _create_test_note(producer="Producer B", vintage=2019))
            _insert_note(session, _create_test_note(producer="Producer C", vintage=2020))
            session.commit()

            service = ExportService(session)
            csv_content = service.export_notes_csv()

            lines = csv_content.strip().split("\n")
            assert len(lines) == 4  # Header + 3 data rows

    def test_export_csv_status_filter(self, test_db):
        """CSV export respects status filter."""
        with test_db() as session:
            _insert_note(session, _create_test_note(producer="Published", status="published"))
            _insert_note(session, _create_test_note(producer="Draft", status="draft"))
            session.commit()

            service = ExportService(session)

            # Default (published only)
            csv_content = service.export_notes_csv()
            assert "Published" in csv_content
            assert "Draft" not in csv_content

            # All statuses
            csv_content = service.export_notes_csv(status="all")
            assert "Published" in csv_content
            assert "Draft" in csv_content

    def test_export_csv_grapes_pipe_separated(self, test_db):
        """CSV export uses pipe separator for grapes."""
        with test_db() as session:
            note = _create_test_note(grapes=["Cabernet Sauvignon", "Merlot"])
            _insert_note(session, note)
            session.commit()

            service = ExportService(session)
            csv_content = service.export_notes_csv()

            assert "Cabernet Sauvignon|Merlot" in csv_content


class TestExportJSON:
    """Tests for JSON export functionality."""

    def test_export_json_structure(self, test_db):
        """JSON export has correct structure."""
        with test_db() as session:
            note = _create_test_note()
            _insert_note(session, note)
            session.commit()

            service = ExportService(session)
            json_content = service.export_notes_json()

            data = json.loads(json_content)
            assert "export_version" in data
            assert "export_date" in data
            assert "count" in data
            assert "notes" in data
            assert data["count"] == 1

    def test_export_json_note_data(self, test_db):
        """JSON export contains correct note data."""
        with test_db() as session:
            note = _create_test_note(
                producer="Penfolds",
                cuvee="Grange",
                vintage=2018,
            )
            _insert_note(session, note)
            session.commit()

            service = ExportService(session)
            json_content = service.export_notes_json()

            data = json.loads(json_content)
            exported_note = data["notes"][0]

            assert exported_note["wine"]["producer"] == "Penfolds"
            assert exported_note["wine"]["cuvee"] == "Grange"
            assert exported_note["wine"]["vintage"] == 2018

    def test_export_json_validates_as_tasting_note(self, test_db):
        """Exported JSON can be parsed back as TastingNote."""
        with test_db() as session:
            note = _create_test_note()
            _insert_note(session, note)
            session.commit()

            service = ExportService(session)
            json_content = service.export_notes_json()

            data = json.loads(json_content)
            # Should not raise
            parsed_note = TastingNote.model_validate(data["notes"][0])
            assert parsed_note.wine.producer == "Domaine de la Romanée-Conti"

    def test_export_json_multiple_notes(self, test_db):
        """JSON export handles multiple notes."""
        with test_db() as session:
            _insert_note(session, _create_test_note(producer="Producer A"))
            _insert_note(session, _create_test_note(producer="Producer B"))
            session.commit()

            service = ExportService(session)
            json_content = service.export_notes_json()

            data = json.loads(json_content)
            assert data["count"] == 2
            assert len(data["notes"]) == 2

    def test_export_json_status_filter(self, test_db):
        """JSON export respects status filter."""
        with test_db() as session:
            _insert_note(session, _create_test_note(producer="Published", status="published"))
            _insert_note(session, _create_test_note(producer="Draft", status="draft"))
            session.commit()

            service = ExportService(session)

            # Default (published only)
            json_content = service.export_notes_json()
            data = json.loads(json_content)
            assert data["count"] == 1
            assert data["notes"][0]["wine"]["producer"] == "Published"

            # Drafts only
            json_content = service.export_notes_json(status="draft")
            data = json.loads(json_content)
            assert data["count"] == 1
            assert data["notes"][0]["wine"]["producer"] == "Draft"

    def test_export_json_specific_notes(self, test_db):
        """JSON export can export specific notes by ID."""
        with test_db() as session:
            note1 = _insert_note(session, _create_test_note(producer="Producer A"))
            _insert_note(session, _create_test_note(producer="Producer B"))
            note3 = _insert_note(session, _create_test_note(producer="Producer C"))
            session.commit()

            service = ExportService(session)
            json_content = service.export_notes_json(note_ids=[note1.id, note3.id])

            data = json.loads(json_content)
            assert data["count"] == 2
            producers = [n["wine"]["producer"] for n in data["notes"]]
            assert "Producer A" in producers
            assert "Producer C" in producers
            assert "Producer B" not in producers
