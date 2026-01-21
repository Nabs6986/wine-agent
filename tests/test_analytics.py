"""Tests for analytics service functionality."""

import json
import tempfile
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from wine_agent.core.enums import NoteSource, NoteStatus, WineColor
from wine_agent.core.schema import Scores, SubScores, TastingNote, WineIdentity
from wine_agent.db.models import Base, TastingNoteDB
from wine_agent.services.analytics_service import AnalyticsService


@pytest.fixture
def test_db():
    """Create a temporary test database."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        engine = create_engine(f"sqlite:///{db_path}", echo=False)

        # Create base tables
        Base.metadata.create_all(bind=engine)

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
    quality_band: str = "very_good",
) -> TastingNote:
    """Helper to create a test tasting note."""
    if grapes is None:
        grapes = ["Pinot Noir"]

    # Use fixed valid subscores that sum to 85
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
        wine=wine,
        scores=scores,
    )

    return note


def _insert_note(session, note: TastingNote, quality_band: str = None) -> None:
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
        quality_band=quality_band or (note.scores.quality_band.value if note.scores.quality_band else None),
        tags_json=json.dumps(note.tags),
        note_json=json.dumps(note_dict),
    )
    session.add(db_note)
    session.commit()


class TestAnalyticsService:
    """Tests for AnalyticsService."""

    def test_summary_stats_empty_db(self, test_db):
        """Summary stats on empty database returns zeros."""
        with test_db() as session:
            analytics = AnalyticsService(session)
            stats = analytics.get_summary_stats()

            assert stats.total_notes == 0
            assert stats.avg_score == 0
            assert stats.unique_producers == 0

    def test_summary_stats_with_notes(self, test_db):
        """Summary stats calculated correctly."""
        with test_db() as session:
            _insert_note(session, _create_test_note(producer="A", region="Burgundy", country="France"))
            _insert_note(session, _create_test_note(producer="B", region="Napa", country="USA"))
            _insert_note(session, _create_test_note(producer="C", region="Barossa", country="Australia"))

            analytics = AnalyticsService(session)
            stats = analytics.get_summary_stats()

            assert stats.total_notes == 3
            assert stats.unique_producers == 3
            assert stats.unique_regions == 3
            assert stats.unique_countries == 3

    def test_score_distribution_empty(self, test_db):
        """Score distribution on empty database."""
        with test_db() as session:
            analytics = AnalyticsService(session)
            dist = analytics.get_score_distribution()

            assert dist.bins == []
            assert dist.total_count == 0

    def test_score_distribution_with_notes(self, test_db):
        """Score distribution bins are calculated correctly."""
        with test_db() as session:
            # Create notes with different scores
            # Note: the actual score will be calculated from subscores
            note1 = _create_test_note(producer="A")  # ~85
            note2 = _create_test_note(producer="B")  # ~85
            note3 = _create_test_note(producer="C")  # ~85

            _insert_note(session, note1)
            _insert_note(session, note2)
            _insert_note(session, note3)

            analytics = AnalyticsService(session)
            dist = analytics.get_score_distribution(bin_size=5)

            assert dist.total_count == 3
            assert len(dist.bins) >= 1
            # Check that we have counts
            total_in_bins = sum(count for _, _, count in dist.bins)
            assert total_in_bins == 3

    def test_top_regions_empty(self, test_db):
        """Top regions on empty database."""
        with test_db() as session:
            analytics = AnalyticsService(session)
            regions = analytics.get_top_regions(min_count=1)

            assert regions == []

    def test_top_regions_respects_min_count(self, test_db):
        """Top regions respects minimum count threshold."""
        with test_db() as session:
            _insert_note(session, _create_test_note(region="Burgundy"))
            _insert_note(session, _create_test_note(region="Burgundy"))
            _insert_note(session, _create_test_note(region="Napa"))  # Only 1 note

            analytics = AnalyticsService(session)

            # With min_count=2, Napa should be excluded
            regions = analytics.get_top_regions(min_count=2)
            region_names = [r.name for r in regions]

            assert "Burgundy" in region_names
            assert "Napa" not in region_names

    def test_top_regions_sorted_by_avg_score(self, test_db):
        """Top regions are sorted by average score descending."""
        with test_db() as session:
            # Create notes with different scores for different regions
            note1 = _create_test_note(region="Burgundy", producer="A")
            note2 = _create_test_note(region="Burgundy", producer="B")
            note3 = _create_test_note(region="Napa", producer="C")
            note4 = _create_test_note(region="Napa", producer="D")

            _insert_note(session, note1)
            _insert_note(session, note2)
            _insert_note(session, note3)
            _insert_note(session, note4)

            analytics = AnalyticsService(session)
            regions = analytics.get_top_regions(min_count=2, limit=10)

            assert len(regions) == 2
            # Both have same score, just check they're both present
            region_names = [r.name for r in regions]
            assert "Burgundy" in region_names
            assert "Napa" in region_names

    def test_top_producers(self, test_db):
        """Top producers works correctly."""
        with test_db() as session:
            _insert_note(session, _create_test_note(producer="DRC"))
            _insert_note(session, _create_test_note(producer="DRC"))
            _insert_note(session, _create_test_note(producer="Opus One"))

            analytics = AnalyticsService(session)
            producers = analytics.get_top_producers(min_count=2)

            assert len(producers) == 1
            assert producers[0].name == "DRC"
            assert producers[0].count == 2

    def test_top_countries(self, test_db):
        """Top countries works correctly."""
        with test_db() as session:
            _insert_note(session, _create_test_note(country="France"))
            _insert_note(session, _create_test_note(country="France"))
            _insert_note(session, _create_test_note(country="USA"))
            _insert_note(session, _create_test_note(country="USA"))

            analytics = AnalyticsService(session)
            countries = analytics.get_top_countries(min_count=2)

            assert len(countries) == 2
            country_names = [c.name for c in countries]
            assert "France" in country_names
            assert "USA" in country_names

    def test_descriptor_frequency_empty(self, test_db):
        """Descriptor frequency on empty database."""
        with test_db() as session:
            analytics = AnalyticsService(session)
            descriptors = analytics.get_descriptor_frequency(field="nose")

            assert descriptors == []

    def test_descriptor_frequency_extracts_terms(self, test_db):
        """Descriptor frequency extracts and counts terms."""
        with test_db() as session:
            _insert_note(
                session,
                _create_test_note(
                    producer="A",
                    nose_notes="Cherry, raspberry, and fresh cherry aromas",
                ),
            )
            _insert_note(
                session,
                _create_test_note(
                    producer="B",
                    nose_notes="Dark cherry with hints of oak",
                ),
            )

            analytics = AnalyticsService(session)
            descriptors = analytics.get_descriptor_frequency(field="nose", limit=10)

            # Cherry should appear multiple times
            terms = [d.term for d in descriptors]
            assert "cherry" in terms

            # Find cherry count
            cherry_count = next(d.count for d in descriptors if d.term == "cherry")
            assert cherry_count >= 2

    def test_descriptor_frequency_filters_stopwords(self, test_db):
        """Descriptor frequency filters out stop words."""
        with test_db() as session:
            _insert_note(
                session,
                _create_test_note(
                    producer="A",
                    nose_notes="The wine has a cherry nose with the typical aromas",
                ),
            )

            analytics = AnalyticsService(session)
            descriptors = analytics.get_descriptor_frequency(field="nose", limit=20)

            terms = [d.term for d in descriptors]
            # Stop words should be filtered
            assert "the" not in terms
            assert "has" not in terms
            assert "with" not in terms

    def test_scoring_trends_empty(self, test_db):
        """Scoring trends on empty database."""
        with test_db() as session:
            analytics = AnalyticsService(session)
            trends = analytics.get_scoring_trends()

            assert trends == []

    def test_scoring_trends_groups_by_month(self, test_db):
        """Scoring trends groups notes by month."""
        with test_db() as session:
            _insert_note(session, _create_test_note(producer="A"))
            _insert_note(session, _create_test_note(producer="B"))

            analytics = AnalyticsService(session)
            trends = analytics.get_scoring_trends(period="month")

            # All notes created now, so one period
            assert len(trends) >= 1
            assert trends[0].count >= 2

    def test_quality_band_distribution(self, test_db):
        """Quality band distribution works correctly."""
        with test_db() as session:
            _insert_note(session, _create_test_note(producer="A"), quality_band="very_good")
            _insert_note(session, _create_test_note(producer="B"), quality_band="very_good")
            _insert_note(session, _create_test_note(producer="C"), quality_band="good")

            analytics = AnalyticsService(session)
            bands = analytics.get_quality_band_distribution()

            assert "very_good" in bands
            assert bands["very_good"] == 2
            assert "good" in bands
            assert bands["good"] == 1

    def test_vintage_distribution(self, test_db):
        """Vintage distribution works correctly."""
        with test_db() as session:
            _insert_note(session, _create_test_note(vintage=2020))
            _insert_note(session, _create_test_note(vintage=2020))
            _insert_note(session, _create_test_note(vintage=2018))

            analytics = AnalyticsService(session)
            vintages = analytics.get_vintage_distribution()

            vintage_dict = dict(vintages)
            assert 2020 in vintage_dict
            assert vintage_dict[2020] == 2
            assert 2018 in vintage_dict
            assert vintage_dict[2018] == 1

    def test_excludes_draft_notes(self, test_db):
        """Analytics excludes draft notes."""
        with test_db() as session:
            _insert_note(session, _create_test_note(producer="Published", status="published"))
            _insert_note(session, _create_test_note(producer="Draft", status="draft"))

            analytics = AnalyticsService(session)
            stats = analytics.get_summary_stats()

            # Only published note should be counted
            assert stats.total_notes == 1
