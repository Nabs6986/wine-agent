"""Tests for search repository functionality."""

import json
import tempfile
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from wine_agent.core.enums import NoteSource, NoteStatus, WineColor
from wine_agent.core.schema import TastingNote
from wine_agent.db.models import Base, TastingNoteDB
from wine_agent.db.search import SearchFilters, SearchRepository


@pytest.fixture
def test_db():
    """Create a temporary test database with FTS support."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        engine = create_engine(f"sqlite:///{db_path}", echo=False)

        # Create base tables
        Base.metadata.create_all(bind=engine)

        # Create FTS5 table manually for testing
        with engine.connect() as conn:
            conn.execute(text("""
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
            """))

            # Create triggers
            conn.execute(text("""
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
            """))
            conn.commit()

        Session = sessionmaker(bind=engine)
        yield Session


def _create_test_note(
    producer: str = "Test Producer",
    cuvee: str = "Test Cuvee",
    region: str = "Burgundy",
    country: str = "France",
    vintage: int = 2020,
    grapes: list[str] = None,
    score_total: int = 85,
    status: str = "published",
    nose_notes: str = "",
    palate_notes: str = "",
    conclusion: str = "",
) -> TastingNote:
    """Helper to create a test tasting note."""
    from wine_agent.core.schema import Scores, SubScores, WineIdentity

    if grapes is None:
        grapes = ["Pinot Noir"]

    # Create scores with subscores so the validator calculates total
    subscores = SubScores(
        appearance=2,
        nose=10,
        palate=17,
        structure_balance=17,
        finish=8,
        typicity_complexity=14,
        overall_judgment=17,
    )
    scores = Scores(subscores=subscores)  # Total = 85

    wine = WineIdentity(
        producer=producer,
        cuvee=cuvee,
        region=region,
        country=country,
        vintage=vintage,
        grapes=grapes,
        color=WineColor.RED,
    )

    note = TastingNote(
        source=NoteSource.MANUAL,
        status=NoteStatus(status),
        nose_notes=nose_notes,
        palate_notes=palate_notes,
        conclusion=conclusion,
        wine=wine,
        scores=scores,
    )

    return note


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
    session.add(db_note)
    session.commit()


class TestSearchRepository:
    """Tests for SearchRepository."""

    def test_search_empty_db(self, test_db):
        """Search on empty database returns empty result."""
        with test_db() as session:
            repo = SearchRepository(session)
            result = repo.search()

            assert result.notes == []
            assert result.total_count == 0

    def test_search_returns_all_published(self, test_db):
        """Search without filters returns all published notes."""
        with test_db() as session:
            # Insert test notes
            _insert_note(session, _create_test_note(producer="Producer A"))
            _insert_note(session, _create_test_note(producer="Producer B"))
            _insert_note(session, _create_test_note(producer="Draft", status="draft"))

            repo = SearchRepository(session)
            result = repo.search()

            assert result.total_count == 2
            assert len(result.notes) == 2
            producers = [n.wine.producer for n in result.notes]
            assert "Draft" not in producers

    def test_search_by_text_query(self, test_db):
        """Text search finds matching notes."""
        with test_db() as session:
            _insert_note(
                session,
                _create_test_note(
                    producer="Domaine Leflaive",
                    region="Burgundy",
                    nose_notes="Fresh cherry and raspberry notes",
                ),
            )
            _insert_note(
                session,
                _create_test_note(
                    producer="Opus One",
                    region="Napa Valley",
                    nose_notes="Dark fruit and cassis",
                ),
            )

            repo = SearchRepository(session)

            # Search for Burgundy
            filters = SearchFilters(query="Burgundy")
            result = repo.search(filters=filters)
            assert result.total_count == 1
            assert result.notes[0].wine.producer == "Domaine Leflaive"

            # Search for cherry
            filters = SearchFilters(query="cherry")
            result = repo.search(filters=filters)
            assert result.total_count == 1

    def test_search_by_score_range(self, test_db):
        """Score range filter works correctly."""
        from wine_agent.core.schema import Scores, SubScores

        with test_db() as session:
            # Create a low-score note (total = 48)
            low_subscores = SubScores(
                appearance=1,
                nose=5,
                palate=10,
                structure_balance=10,
                finish=4,
                typicity_complexity=8,
                overall_judgment=10,
            )
            low_scores = Scores(subscores=low_subscores)

            note1 = TastingNote(
                source=NoteSource.MANUAL,
                status=NoteStatus.PUBLISHED,
                scores=low_scores,
            )
            note1.wine.producer = "Low Score"
            note1.wine.color = WineColor.RED
            _insert_note(session, note1)  # Total = 48

            # High score note (default from _create_test_note = 85)
            note2 = _create_test_note(producer="High Score")
            _insert_note(session, note2)

            repo = SearchRepository(session)

            # Filter by minimum score 80
            filters = SearchFilters(score_min=80)
            result = repo.search(filters=filters)
            assert result.total_count == 1
            assert result.notes[0].wine.producer == "High Score"

    def test_search_by_region(self, test_db):
        """Region filter works correctly."""
        with test_db() as session:
            _insert_note(session, _create_test_note(region="Burgundy"))
            _insert_note(session, _create_test_note(region="Bordeaux"))

            repo = SearchRepository(session)
            filters = SearchFilters(region="Burgundy")
            result = repo.search(filters=filters)

            assert result.total_count == 1
            assert result.notes[0].wine.region == "Burgundy"

    def test_search_by_country(self, test_db):
        """Country filter works correctly."""
        with test_db() as session:
            _insert_note(session, _create_test_note(country="France"))
            _insert_note(session, _create_test_note(country="Italy"))

            repo = SearchRepository(session)
            filters = SearchFilters(country="France")
            result = repo.search(filters=filters)

            assert result.total_count == 1
            assert result.notes[0].wine.country == "France"

    def test_search_by_producer(self, test_db):
        """Producer filter works correctly."""
        with test_db() as session:
            _insert_note(session, _create_test_note(producer="Domaine Leroy"))
            _insert_note(session, _create_test_note(producer="Opus One"))

            repo = SearchRepository(session)
            filters = SearchFilters(producer="Leroy")
            result = repo.search(filters=filters)

            assert result.total_count == 1
            assert "Leroy" in result.notes[0].wine.producer

    def test_search_by_vintage_range(self, test_db):
        """Vintage range filter works correctly."""
        with test_db() as session:
            _insert_note(session, _create_test_note(vintage=2018))
            _insert_note(session, _create_test_note(vintage=2020))
            _insert_note(session, _create_test_note(vintage=2022))

            repo = SearchRepository(session)
            filters = SearchFilters(vintage_min=2019, vintage_max=2021)
            result = repo.search(filters=filters)

            assert result.total_count == 1
            assert result.notes[0].wine.vintage == 2020

    def test_search_pagination(self, test_db):
        """Pagination works correctly."""
        with test_db() as session:
            # Insert 5 notes
            for i in range(5):
                _insert_note(session, _create_test_note(producer=f"Producer {i}"))

            repo = SearchRepository(session)

            # First page
            result = repo.search(limit=2, offset=0)
            assert len(result.notes) == 2
            assert result.total_count == 5
            assert result.page == 1
            assert result.total_pages == 3
            assert result.has_more is True

            # Second page
            result = repo.search(limit=2, offset=2)
            assert len(result.notes) == 2
            assert result.page == 2

            # Last page
            result = repo.search(limit=2, offset=4)
            assert len(result.notes) == 1
            assert result.has_more is False

    def test_search_combined_filters(self, test_db):
        """Multiple filters combine correctly."""
        with test_db() as session:
            _insert_note(
                session,
                _create_test_note(
                    producer="Target",
                    country="France",
                    region="Burgundy",
                    vintage=2020,
                ),
            )
            _insert_note(
                session,
                _create_test_note(
                    producer="Other",
                    country="France",
                    region="Bordeaux",
                    vintage=2020,
                ),
            )
            _insert_note(
                session,
                _create_test_note(
                    producer="Another",
                    country="Italy",
                    region="Tuscany",
                    vintage=2020,
                ),
            )

            repo = SearchRepository(session)
            filters = SearchFilters(country="France", region="Burgundy")
            result = repo.search(filters=filters)

            assert result.total_count == 1
            assert result.notes[0].wine.producer == "Target"

    def test_get_filter_options(self, test_db):
        """Filter options are retrieved correctly."""
        with test_db() as session:
            _insert_note(
                session,
                _create_test_note(
                    producer="Producer A",
                    region="Burgundy",
                    country="France",
                    grapes=["Pinot Noir", "Chardonnay"],
                ),
            )
            _insert_note(
                session,
                _create_test_note(
                    producer="Producer B",
                    region="Napa",
                    country="USA",
                    grapes=["Cabernet Sauvignon"],
                ),
            )

            repo = SearchRepository(session)
            options = repo.get_filter_options()

            assert "Burgundy" in options["regions"]
            assert "Napa" in options["regions"]
            assert "France" in options["countries"]
            assert "USA" in options["countries"]
            assert "Producer A" in options["producers"]
            assert "Pinot Noir" in options["grapes"]
            assert "Cabernet Sauvignon" in options["grapes"]

    def test_search_all_statuses(self, test_db):
        """Search with status='all' returns both drafts and published."""
        with test_db() as session:
            _insert_note(session, _create_test_note(producer="Published", status="published"))
            _insert_note(session, _create_test_note(producer="Draft", status="draft"))

            repo = SearchRepository(session)
            filters = SearchFilters(status="all")
            result = repo.search(filters=filters)

            assert result.total_count == 2

    def test_search_drafts_only(self, test_db):
        """Search with status='draft' returns only drafts."""
        with test_db() as session:
            _insert_note(session, _create_test_note(producer="Published", status="published"))
            _insert_note(session, _create_test_note(producer="Draft", status="draft"))

            repo = SearchRepository(session)
            filters = SearchFilters(status="draft")
            result = repo.search(filters=filters)

            assert result.total_count == 1
            assert result.notes[0].wine.producer == "Draft"
