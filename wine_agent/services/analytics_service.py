"""Analytics service for Wine Agent.

Provides aggregation and statistical analysis of tasting notes.
"""

import re
from collections import Counter
from dataclasses import dataclass
from statistics import mean, median, stdev

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from wine_agent.db.models import TastingNoteDB


# Common stop words to exclude from descriptor frequency
STOP_WORDS = {
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "as", "is", "was", "are", "were", "been",
    "be", "have", "has", "had", "do", "does", "did", "will", "would",
    "could", "should", "may", "might", "must", "shall", "can", "need",
    "this", "that", "these", "those", "it", "its", "very", "quite",
    "some", "good", "nice", "well", "also", "just", "more", "most",
    "other", "into", "over", "such", "no", "not", "only", "same",
    "than", "too", "so", "out", "up", "down", "off", "all", "any",
    "both", "each", "few", "many", "much", "own", "which", "who",
    "whom", "whose", "what", "when", "where", "why", "how", "there",
}


@dataclass
class ScoreDistribution:
    """Score distribution statistics."""

    bins: list[tuple[int, int, int]]  # (min, max, count)
    mean: float
    median: float
    std_dev: float
    total_count: int


@dataclass
class TopEntity:
    """A top-ranked entity (region, producer, etc.)."""

    name: str
    count: int
    avg_score: float


@dataclass
class DescriptorFrequency:
    """Frequency of a descriptor term."""

    term: str
    count: int


@dataclass
class ScoringTrend:
    """Scoring trend for a time period."""

    period: str  # e.g., "2024-01" for monthly
    count: int
    avg_score: float


@dataclass
class SummaryStats:
    """Summary statistics for the collection."""

    total_notes: int
    avg_score: float
    min_score: int
    max_score: int
    unique_producers: int
    unique_regions: int
    unique_countries: int
    date_range: tuple[str, str] | None  # (earliest, latest)


class AnalyticsService:
    """Service for analytics and aggregation queries."""

    def __init__(self, session: Session):
        """Initialize with a database session."""
        self.session = session

    def get_summary_stats(self) -> SummaryStats:
        """Get summary statistics for all published notes."""
        # Query for basic stats
        result = self.session.execute(
            text("""
                SELECT
                    COUNT(*) as total,
                    COALESCE(AVG(score_total), 0) as avg_score,
                    COALESCE(MIN(score_total), 0) as min_score,
                    COALESCE(MAX(score_total), 0) as max_score,
                    COUNT(DISTINCT producer) as unique_producers,
                    COUNT(DISTINCT region) as unique_regions,
                    COUNT(DISTINCT country) as unique_countries,
                    MIN(created_at) as earliest,
                    MAX(created_at) as latest
                FROM tasting_notes
                WHERE status = 'published'
            """)
        ).fetchone()

        date_range = None
        if result.earliest and result.latest:
            earliest = result.earliest[:10] if isinstance(result.earliest, str) else result.earliest.strftime("%Y-%m-%d")
            latest = result.latest[:10] if isinstance(result.latest, str) else result.latest.strftime("%Y-%m-%d")
            date_range = (earliest, latest)

        return SummaryStats(
            total_notes=result.total or 0,
            avg_score=round(result.avg_score or 0, 1),
            min_score=result.min_score or 0,
            max_score=result.max_score or 0,
            unique_producers=result.unique_producers or 0,
            unique_regions=result.unique_regions or 0,
            unique_countries=result.unique_countries or 0,
            date_range=date_range,
        )

    def get_score_distribution(self, bin_size: int = 5) -> ScoreDistribution:
        """
        Get score distribution in bins.

        Args:
            bin_size: Size of each bin (default 5, e.g., 50-55, 55-60, ...).

        Returns:
            ScoreDistribution with bins, mean, median, std_dev.
        """
        # Get all scores
        scores = [
            row.score_total
            for row in self.session.query(TastingNoteDB.score_total)
            .filter(TastingNoteDB.status == "published")
            .all()
        ]

        if not scores:
            return ScoreDistribution(
                bins=[],
                mean=0.0,
                median=0.0,
                std_dev=0.0,
                total_count=0,
            )

        # Calculate statistics
        score_mean = mean(scores)
        score_median = median(scores)
        score_std_dev = stdev(scores) if len(scores) > 1 else 0.0

        # Create bins (0-100 range)
        bin_counts: dict[int, int] = {}
        for score in scores:
            bin_start = (score // bin_size) * bin_size
            bin_counts[bin_start] = bin_counts.get(bin_start, 0) + 1

        # Build sorted bins list
        bins = [
            (bin_start, bin_start + bin_size - 1, count)
            for bin_start, count in sorted(bin_counts.items())
        ]

        return ScoreDistribution(
            bins=bins,
            mean=round(score_mean, 1),
            median=round(score_median, 1),
            std_dev=round(score_std_dev, 1),
            total_count=len(scores),
        )

    def get_top_regions(self, min_count: int = 2, limit: int = 10) -> list[TopEntity]:
        """
        Get regions with highest average scores.

        Args:
            min_count: Minimum number of notes required for inclusion.
            limit: Maximum number of results.

        Returns:
            List of TopEntity sorted by average score descending.
        """
        result = self.session.execute(
            text("""
                SELECT region, COUNT(*) as count, AVG(score_total) as avg_score
                FROM tasting_notes
                WHERE status = 'published' AND region != ''
                GROUP BY region
                HAVING count >= :min_count
                ORDER BY avg_score DESC
                LIMIT :limit
            """),
            {"min_count": min_count, "limit": limit},
        ).fetchall()

        return [
            TopEntity(name=row.region, count=row.count, avg_score=round(row.avg_score, 1))
            for row in result
        ]

    def get_top_producers(self, min_count: int = 2, limit: int = 10) -> list[TopEntity]:
        """
        Get producers with highest average scores.

        Args:
            min_count: Minimum number of notes required for inclusion.
            limit: Maximum number of results.

        Returns:
            List of TopEntity sorted by average score descending.
        """
        result = self.session.execute(
            text("""
                SELECT producer, COUNT(*) as count, AVG(score_total) as avg_score
                FROM tasting_notes
                WHERE status = 'published' AND producer != ''
                GROUP BY producer
                HAVING count >= :min_count
                ORDER BY avg_score DESC
                LIMIT :limit
            """),
            {"min_count": min_count, "limit": limit},
        ).fetchall()

        return [
            TopEntity(name=row.producer, count=row.count, avg_score=round(row.avg_score, 1))
            for row in result
        ]

    def get_top_countries(self, min_count: int = 2, limit: int = 10) -> list[TopEntity]:
        """
        Get countries with highest average scores.

        Args:
            min_count: Minimum number of notes required for inclusion.
            limit: Maximum number of results.

        Returns:
            List of TopEntity sorted by average score descending.
        """
        result = self.session.execute(
            text("""
                SELECT country, COUNT(*) as count, AVG(score_total) as avg_score
                FROM tasting_notes
                WHERE status = 'published' AND country != ''
                GROUP BY country
                HAVING count >= :min_count
                ORDER BY avg_score DESC
                LIMIT :limit
            """),
            {"min_count": min_count, "limit": limit},
        ).fetchall()

        return [
            TopEntity(name=row.country, count=row.count, avg_score=round(row.avg_score, 1))
            for row in result
        ]

    def get_descriptor_frequency(
        self, field: str = "nose", limit: int = 30
    ) -> list[DescriptorFrequency]:
        """
        Get most frequent descriptor terms from notes.

        Args:
            field: Field to analyze ("nose" for nose_notes, "palate" for palate_notes).
            limit: Maximum number of terms to return.

        Returns:
            List of DescriptorFrequency sorted by count descending.
        """
        # Determine which JSON path to extract
        json_path = "$.nose_notes" if field == "nose" else "$.palate_notes"

        # Get all text from the specified field
        result = self.session.execute(
            text(f"""
                SELECT json_extract(note_json, '{json_path}') as notes_text
                FROM tasting_notes
                WHERE status = 'published'
            """)
        ).fetchall()

        # Tokenize and count words
        word_counter: Counter[str] = Counter()

        for row in result:
            if row.notes_text:
                # Tokenize: lowercase, split on non-alphanumeric
                words = re.findall(r"[a-z]+", row.notes_text.lower())
                # Filter stop words and short words
                words = [w for w in words if w not in STOP_WORDS and len(w) > 2]
                word_counter.update(words)

        # Return top N
        return [
            DescriptorFrequency(term=term, count=count)
            for term, count in word_counter.most_common(limit)
        ]

    def get_scoring_trends(self, period: str = "month") -> list[ScoringTrend]:
        """
        Get average scores over time.

        Args:
            period: Aggregation period ("month" or "year").

        Returns:
            List of ScoringTrend sorted by period ascending.
        """
        if period == "year":
            date_format = "%Y"
        else:
            date_format = "%Y-%m"

        result = self.session.execute(
            text(f"""
                SELECT
                    strftime('{date_format}', created_at) as period,
                    COUNT(*) as count,
                    AVG(score_total) as avg_score
                FROM tasting_notes
                WHERE status = 'published'
                GROUP BY period
                ORDER BY period ASC
            """)
        ).fetchall()

        return [
            ScoringTrend(
                period=row.period,
                count=row.count,
                avg_score=round(row.avg_score, 1),
            )
            for row in result
        ]

    def get_quality_band_distribution(self) -> dict[str, int]:
        """Get count of notes per quality band."""
        result = self.session.execute(
            text("""
                SELECT quality_band, COUNT(*) as count
                FROM tasting_notes
                WHERE status = 'published' AND quality_band IS NOT NULL
                GROUP BY quality_band
                ORDER BY count DESC
            """)
        ).fetchall()

        return {row.quality_band: row.count for row in result}

    def get_vintage_distribution(self) -> list[tuple[int, int]]:
        """Get count of notes per vintage year."""
        result = self.session.execute(
            text("""
                SELECT vintage, COUNT(*) as count
                FROM tasting_notes
                WHERE status = 'published' AND vintage IS NOT NULL
                GROUP BY vintage
                ORDER BY vintage DESC
            """)
        ).fetchall()

        return [(row.vintage, row.count) for row in result]
