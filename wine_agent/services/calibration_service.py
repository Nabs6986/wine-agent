"""Calibration service for Wine Agent.

Manages user-defined score calibration notes and personal scoring statistics.
"""

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from statistics import mean, stdev
from uuid import UUID, uuid4

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from wine_agent.db.models import CalibrationNoteDB, TastingNoteDB


@dataclass
class CalibrationNote:
    """A calibration note for a score level."""

    id: UUID
    score_value: int
    description: str
    examples: list[str]
    created_at: datetime
    updated_at: datetime


@dataclass
class PersonalStats:
    """Personal scoring statistics."""

    total_notes: int
    avg_score: float
    std_dev: float
    score_range: tuple[int, int]
    notes_this_month: int
    avg_score_this_month: float


@dataclass
class ScoreConsistency:
    """Score consistency analysis."""

    overall_std_dev: float
    by_region: dict[str, float]  # region -> std_dev
    by_country: dict[str, float]  # country -> std_dev


class CalibrationService:
    """Service for calibration notes and scoring analysis."""

    def __init__(self, session: Session):
        """Initialize with a database session."""
        self.session = session

    def get_calibration_notes(self) -> list[CalibrationNote]:
        """
        Get all calibration notes ordered by score value.

        Returns:
            List of calibration notes sorted by score_value ascending.
        """
        db_notes = (
            self.session.query(CalibrationNoteDB)
            .order_by(CalibrationNoteDB.score_value.asc())
            .all()
        )

        return [self._to_domain(db_note) for db_note in db_notes]

    def get_calibration_note(self, note_id: str) -> CalibrationNote | None:
        """
        Get a specific calibration note by ID.

        Args:
            note_id: The UUID of the calibration note.

        Returns:
            The calibration note if found, None otherwise.
        """
        db_note = self.session.query(CalibrationNoteDB).filter_by(id=note_id).first()
        return self._to_domain(db_note) if db_note else None

    def get_calibration_note_by_score(self, score_value: int) -> CalibrationNote | None:
        """
        Get a calibration note for a specific score value.

        Args:
            score_value: The score value (e.g., 70, 80, 90).

        Returns:
            The calibration note if found, None otherwise.
        """
        db_note = (
            self.session.query(CalibrationNoteDB)
            .filter_by(score_value=score_value)
            .first()
        )
        return self._to_domain(db_note) if db_note else None

    def set_calibration_note(
        self,
        score_value: int,
        description: str,
        examples: list[str] | None = None,
        note_id: str | None = None,
    ) -> CalibrationNote:
        """
        Create or update a calibration note for a score level.

        If note_id is provided, updates that specific note.
        Otherwise, creates a new note (or updates existing for that score_value).

        Args:
            score_value: The score value (e.g., 70, 80, 90).
            description: Description of what this score means.
            examples: Optional list of example wine names.
            note_id: Optional ID of existing note to update.

        Returns:
            The created or updated calibration note.
        """
        examples = examples or []
        now = datetime.now(UTC)

        if note_id:
            # Update by ID
            db_note = self.session.query(CalibrationNoteDB).filter_by(id=note_id).first()
            if db_note:
                db_note.score_value = score_value
                db_note.description = description
                db_note.examples = json.dumps(examples)
                db_note.updated_at = now
                self.session.commit()
                return self._to_domain(db_note)

        # Check if note exists for this score value
        existing = (
            self.session.query(CalibrationNoteDB)
            .filter_by(score_value=score_value)
            .first()
        )

        if existing:
            existing.description = description
            existing.examples = json.dumps(examples)
            existing.updated_at = now
            self.session.commit()
            return self._to_domain(existing)

        # Create new note
        db_note = CalibrationNoteDB(
            id=str(uuid4()),
            score_value=score_value,
            description=description,
            examples=json.dumps(examples),
            created_at=now,
            updated_at=now,
        )
        self.session.add(db_note)
        self.session.commit()

        return self._to_domain(db_note)

    def delete_calibration_note(self, note_id: str) -> bool:
        """
        Delete a calibration note.

        Args:
            note_id: The UUID of the calibration note.

        Returns:
            True if deleted, False if not found.
        """
        db_note = self.session.query(CalibrationNoteDB).filter_by(id=note_id).first()
        if db_note:
            self.session.delete(db_note)
            self.session.commit()
            return True
        return False

    def get_personal_stats(self) -> PersonalStats:
        """
        Get personal scoring statistics.

        Returns:
            PersonalStats with averages and trends.
        """
        # All-time stats
        all_scores = [
            row.score_total
            for row in self.session.query(TastingNoteDB.score_total)
            .filter(TastingNoteDB.status == "published")
            .all()
        ]

        total_notes = len(all_scores)
        avg_score = mean(all_scores) if all_scores else 0.0
        std_dev_val = stdev(all_scores) if len(all_scores) > 1 else 0.0
        score_range = (min(all_scores), max(all_scores)) if all_scores else (0, 0)

        # This month stats
        now = datetime.now(UTC)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        month_scores = [
            row.score_total
            for row in self.session.query(TastingNoteDB.score_total)
            .filter(
                TastingNoteDB.status == "published",
                TastingNoteDB.created_at >= month_start,
            )
            .all()
        ]

        notes_this_month = len(month_scores)
        avg_score_this_month = mean(month_scores) if month_scores else 0.0

        return PersonalStats(
            total_notes=total_notes,
            avg_score=round(avg_score, 1),
            std_dev=round(std_dev_val, 1),
            score_range=score_range,
            notes_this_month=notes_this_month,
            avg_score_this_month=round(avg_score_this_month, 1),
        )

    def get_score_consistency(self) -> ScoreConsistency:
        """
        Analyze scoring consistency across regions and countries.

        Returns:
            ScoreConsistency with standard deviations by category.
        """
        # Overall std dev
        all_scores = [
            row.score_total
            for row in self.session.query(TastingNoteDB.score_total)
            .filter(TastingNoteDB.status == "published")
            .all()
        ]
        overall_std = stdev(all_scores) if len(all_scores) > 1 else 0.0

        # By region (only for regions with 3+ notes)
        region_scores: dict[str, list[int]] = {}
        for row in self.session.query(
            TastingNoteDB.region, TastingNoteDB.score_total
        ).filter(
            TastingNoteDB.status == "published",
            TastingNoteDB.region != "",
        ).all():
            if row.region not in region_scores:
                region_scores[row.region] = []
            region_scores[row.region].append(row.score_total)

        by_region = {
            region: round(stdev(scores), 1)
            for region, scores in region_scores.items()
            if len(scores) >= 3
        }

        # By country (only for countries with 3+ notes)
        country_scores: dict[str, list[int]] = {}
        for row in self.session.query(
            TastingNoteDB.country, TastingNoteDB.score_total
        ).filter(
            TastingNoteDB.status == "published",
            TastingNoteDB.country != "",
        ).all():
            if row.country not in country_scores:
                country_scores[row.country] = []
            country_scores[row.country].append(row.score_total)

        by_country = {
            country: round(stdev(scores), 1)
            for country, scores in country_scores.items()
            if len(scores) >= 3
        }

        return ScoreConsistency(
            overall_std_dev=round(overall_std, 1),
            by_region=by_region,
            by_country=by_country,
        )

    def get_scoring_averages_over_time(self, period: str = "month") -> list[dict]:
        """
        Get personal scoring averages over time.

        Args:
            period: "month" or "year"

        Returns:
            List of dicts with period, count, avg_score.
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
            {
                "period": row.period,
                "count": row.count,
                "avg_score": round(row.avg_score, 1),
            }
            for row in result
        ]

    def _to_domain(self, db_note: CalibrationNoteDB) -> CalibrationNote:
        """Convert database model to domain model."""
        return CalibrationNote(
            id=UUID(db_note.id),
            score_value=db_note.score_value,
            description=db_note.description,
            examples=json.loads(db_note.examples) if db_note.examples else [],
            created_at=db_note.created_at,
            updated_at=db_note.updated_at,
        )
