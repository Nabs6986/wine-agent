"""Scoring calculation and validation for wine tasting notes."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from wine_agent.core.schema import SubScores

from wine_agent.core.enums import QualityBand

SUBSCORE_RANGES: dict[str, tuple[int, int]] = {
    "appearance": (0, 2),
    "nose": (0, 12),
    "palate": (0, 20),
    "structure_balance": (0, 20),
    "finish": (0, 10),
    "typicity_complexity": (0, 16),
    "overall_judgment": (0, 20),
}

MAX_TOTAL_SCORE = 100


def validate_subscore(name: str, value: int) -> None:
    """
    Validate that a subscore is within its allowed range.

    Args:
        name: The subscore field name.
        value: The subscore value.

    Raises:
        ValueError: If the subscore is out of range.
    """
    if name not in SUBSCORE_RANGES:
        raise ValueError(f"Unknown subscore: {name}")

    min_val, max_val = SUBSCORE_RANGES[name]
    if not (min_val <= value <= max_val):
        raise ValueError(
            f"Subscore '{name}' must be between {min_val} and {max_val}, got {value}"
        )


def calculate_total_score(subscores: SubScores) -> int:
    """
    Calculate the total score from subscores.

    The total is the sum of all subscores, with a maximum of 100 points:
    - Appearance: 0-2
    - Nose: 0-12
    - Palate: 0-20
    - Structure & Balance: 0-20
    - Finish: 0-10
    - Typicity & Complexity: 0-16
    - Overall Judgment: 0-20
    Total maximum: 2 + 12 + 20 + 20 + 10 + 16 + 20 = 100

    Args:
        subscores: The SubScores object containing individual scores.

    Returns:
        The total score (0-100).
    """
    total = (
        subscores.appearance
        + subscores.nose
        + subscores.palate
        + subscores.structure_balance
        + subscores.finish
        + subscores.typicity_complexity
        + subscores.overall_judgment
    )
    return min(total, MAX_TOTAL_SCORE)


def determine_quality_band(total_score: int) -> QualityBand:
    """
    Determine the quality band based on total score.

    Quality bands:
    - 0-69: poor
    - 70-79: acceptable
    - 80-89: good
    - 90-94: very good
    - 95-100: outstanding

    Args:
        total_score: The total score (0-100).

    Returns:
        The corresponding QualityBand enum value.
    """
    if total_score < 70:
        return QualityBand.POOR
    elif total_score < 80:
        return QualityBand.ACCEPTABLE
    elif total_score < 90:
        return QualityBand.GOOD
    elif total_score < 95:
        return QualityBand.VERY_GOOD
    else:
        return QualityBand.OUTSTANDING


def validate_all_subscores(subscores: SubScores) -> list[str]:
    """
    Validate all subscores and return a list of validation errors.

    Args:
        subscores: The SubScores object to validate.

    Returns:
        A list of error messages (empty if all valid).
    """
    errors: list[str] = []

    for field_name in SUBSCORE_RANGES:
        value = getattr(subscores, field_name)
        try:
            validate_subscore(field_name, value)
        except ValueError as e:
            errors.append(str(e))

    return errors
