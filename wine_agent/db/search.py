"""Search repository with FTS5 full-text search and filters."""

import json
from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from wine_agent.core.schema import TastingNote


@dataclass
class SearchFilters:
    """Filters for searching tasting notes."""

    query: str | None = None
    score_min: int | None = None
    score_max: int | None = None
    region: str | None = None
    country: str | None = None
    grape: str | None = None
    producer: str | None = None
    vintage_min: int | None = None
    vintage_max: int | None = None
    drink_or_hold: str | None = None
    status: str = "published"


@dataclass
class SearchResult:
    """Result of a search query."""

    notes: list[TastingNote] = field(default_factory=list)
    total_count: int = 0
    limit: int = 50
    offset: int = 0

    @property
    def has_more(self) -> bool:
        """Check if there are more results."""
        return self.offset + len(self.notes) < self.total_count

    @property
    def page(self) -> int:
        """Current page number (1-indexed)."""
        if self.limit == 0:
            return 1
        return (self.offset // self.limit) + 1

    @property
    def total_pages(self) -> int:
        """Total number of pages."""
        if self.limit == 0:
            return 1
        return (self.total_count + self.limit - 1) // self.limit


class SearchRepository:
    """Repository for searching tasting notes with FTS and filters."""

    def __init__(self, session: Session):
        self.session = session

    def search(
        self,
        filters: SearchFilters | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> SearchResult:
        """
        Search tasting notes with full-text search and filters.

        Args:
            filters: Search filters to apply.
            limit: Maximum number of results to return.
            offset: Number of results to skip.

        Returns:
            SearchResult with matching notes and pagination info.
        """
        if filters is None:
            filters = SearchFilters()

        # Build the WHERE clause conditions
        conditions = []
        params: dict = {}

        # Status filter (always applied)
        if filters.status and filters.status != "all":
            conditions.append("tn.status = :status")
            params["status"] = filters.status

        # Score range filters
        if filters.score_min is not None:
            conditions.append("tn.score_total >= :score_min")
            params["score_min"] = filters.score_min

        if filters.score_max is not None:
            conditions.append("tn.score_total <= :score_max")
            params["score_max"] = filters.score_max

        # Region filter (case-insensitive partial match)
        if filters.region:
            conditions.append("LOWER(tn.region) LIKE LOWER(:region)")
            params["region"] = f"%{filters.region}%"

        # Country filter (case-insensitive partial match)
        if filters.country:
            conditions.append("LOWER(tn.country) LIKE LOWER(:country)")
            params["country"] = f"%{filters.country}%"

        # Producer filter (case-insensitive partial match)
        if filters.producer:
            conditions.append("LOWER(tn.producer) LIKE LOWER(:producer)")
            params["producer"] = f"%{filters.producer}%"

        # Grape filter (search in JSON array)
        if filters.grape:
            conditions.append("LOWER(tn.grapes_json) LIKE LOWER(:grape)")
            params["grape"] = f"%{filters.grape}%"

        # Vintage range filters
        if filters.vintage_min is not None:
            conditions.append("tn.vintage >= :vintage_min")
            params["vintage_min"] = filters.vintage_min

        if filters.vintage_max is not None:
            conditions.append("tn.vintage <= :vintage_max")
            params["vintage_max"] = filters.vintage_max

        # Drink or hold filter
        if filters.drink_or_hold:
            conditions.append(
                "json_extract(tn.note_json, '$.readiness.drink_or_hold') = :drink_or_hold"
            )
            params["drink_or_hold"] = filters.drink_or_hold

        # Build the base query
        if filters.query:
            # Use FTS5 for text search
            fts_query = self._build_fts_query(filters.query)
            params["fts_query"] = fts_query

            where_clause = " AND ".join(conditions) if conditions else "1=1"

            # Query with FTS join
            sql = f"""
                SELECT tn.note_json
                FROM tasting_notes tn
                INNER JOIN tasting_notes_fts fts ON tn.id = fts.note_id
                WHERE fts.tasting_notes_fts MATCH :fts_query
                AND {where_clause}
                ORDER BY tn.updated_at DESC
                LIMIT :limit OFFSET :offset
            """

            count_sql = f"""
                SELECT COUNT(*)
                FROM tasting_notes tn
                INNER JOIN tasting_notes_fts fts ON tn.id = fts.note_id
                WHERE fts.tasting_notes_fts MATCH :fts_query
                AND {where_clause}
            """
        else:
            # No text search, just filters
            where_clause = " AND ".join(conditions) if conditions else "1=1"

            sql = f"""
                SELECT tn.note_json
                FROM tasting_notes tn
                WHERE {where_clause}
                ORDER BY tn.updated_at DESC
                LIMIT :limit OFFSET :offset
            """

            count_sql = f"""
                SELECT COUNT(*)
                FROM tasting_notes tn
                WHERE {where_clause}
            """

        params["limit"] = limit
        params["offset"] = offset

        # Execute queries
        result = self.session.execute(text(sql), params)
        rows = result.fetchall()

        count_result = self.session.execute(text(count_sql), params)
        total_count = count_result.scalar() or 0

        # Parse notes from JSON
        notes = []
        for row in rows:
            note_data = json.loads(row[0])
            notes.append(TastingNote.model_validate(note_data))

        return SearchResult(
            notes=notes,
            total_count=total_count,
            limit=limit,
            offset=offset,
        )

    def _build_fts_query(self, query: str) -> str:
        """
        Build an FTS5 query string from user input.

        Handles special characters and builds a prefix search.

        Args:
            query: User's search query.

        Returns:
            FTS5-compatible query string.
        """
        # Clean and escape the query
        # Remove FTS special characters that could cause issues
        cleaned = query.strip()
        special_chars = ['"', "'", "(", ")", "*", ":", "-", "^"]
        for char in special_chars:
            cleaned = cleaned.replace(char, " ")

        # Split into words and create prefix search for each
        words = cleaned.split()
        if not words:
            return '""'

        # Use prefix search for partial matching
        # Each word gets a * suffix for prefix matching
        terms = [f'"{word}"*' for word in words if word]
        return " ".join(terms)

    def get_filter_options(self) -> dict:
        """
        Get available filter options from existing notes.

        Returns a dictionary with lists of unique values for:
        - regions
        - countries
        - producers
        - grapes

        Returns:
            Dictionary of filter options.
        """
        options: dict = {
            "regions": [],
            "countries": [],
            "producers": [],
            "grapes": [],
        }

        # Get unique regions
        result = self.session.execute(
            text(
                "SELECT DISTINCT region FROM tasting_notes WHERE region != '' ORDER BY region"
            )
        )
        options["regions"] = [row[0] for row in result.fetchall()]

        # Get unique countries
        result = self.session.execute(
            text(
                "SELECT DISTINCT country FROM tasting_notes WHERE country != '' ORDER BY country"
            )
        )
        options["countries"] = [row[0] for row in result.fetchall()]

        # Get unique producers
        result = self.session.execute(
            text(
                "SELECT DISTINCT producer FROM tasting_notes WHERE producer != '' ORDER BY producer"
            )
        )
        options["producers"] = [row[0] for row in result.fetchall()]

        # Get unique grapes (from JSON arrays)
        result = self.session.execute(
            text("SELECT DISTINCT grapes_json FROM tasting_notes WHERE grapes_json != '[]'")
        )
        all_grapes = set()
        for row in result.fetchall():
            try:
                grapes = json.loads(row[0])
                all_grapes.update(grapes)
            except (json.JSONDecodeError, TypeError):
                pass
        options["grapes"] = sorted(list(all_grapes))

        return options
