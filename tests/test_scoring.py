"""Tests for scoring calculation and validation."""

import pytest

from wine_agent.core.enums import QualityBand
from wine_agent.core.schema import SubScores
from wine_agent.core.scoring import (
    SUBSCORE_RANGES,
    calculate_total_score,
    determine_quality_band,
    validate_all_subscores,
    validate_subscore,
)


class TestSubscoreRanges:
    """Tests for subscore range definitions."""

    def test_all_ranges_defined(self) -> None:
        """Test that all expected subscores have ranges."""
        expected_fields = [
            "appearance",
            "nose",
            "palate",
            "structure_balance",
            "finish",
            "typicity_complexity",
            "overall_judgment",
        ]
        for field in expected_fields:
            assert field in SUBSCORE_RANGES

    def test_ranges_sum_to_100(self) -> None:
        """Test that maximum subscores sum to 100."""
        max_total = sum(max_val for _, max_val in SUBSCORE_RANGES.values())
        assert max_total == 100


class TestValidateSubscore:
    """Tests for validate_subscore function."""

    def test_valid_appearance(self) -> None:
        """Test valid appearance scores."""
        validate_subscore("appearance", 0)
        validate_subscore("appearance", 1)
        validate_subscore("appearance", 2)

    def test_invalid_appearance_too_high(self) -> None:
        """Test appearance score too high."""
        with pytest.raises(ValueError, match="appearance.*between 0 and 2"):
            validate_subscore("appearance", 3)

    def test_invalid_appearance_negative(self) -> None:
        """Test negative appearance score."""
        with pytest.raises(ValueError, match="appearance.*between 0 and 2"):
            validate_subscore("appearance", -1)

    def test_valid_nose(self) -> None:
        """Test valid nose scores."""
        validate_subscore("nose", 0)
        validate_subscore("nose", 6)
        validate_subscore("nose", 12)

    def test_invalid_nose(self) -> None:
        """Test invalid nose score."""
        with pytest.raises(ValueError, match="nose.*between 0 and 12"):
            validate_subscore("nose", 13)

    def test_unknown_subscore(self) -> None:
        """Test unknown subscore name."""
        with pytest.raises(ValueError, match="Unknown subscore"):
            validate_subscore("unknown_field", 5)


class TestCalculateTotalScore:
    """Tests for calculate_total_score function."""

    def test_all_zeros(self) -> None:
        """Test total with all zeros."""
        subscores = SubScores()
        assert calculate_total_score(subscores) == 0

    def test_maximum_scores(self) -> None:
        """Test total with maximum scores."""
        subscores = SubScores(
            appearance=2,
            nose=12,
            palate=20,
            structure_balance=20,
            finish=10,
            typicity_complexity=16,
            overall_judgment=20,
        )
        assert calculate_total_score(subscores) == 100

    def test_partial_scores(self) -> None:
        """Test total with partial scores."""
        subscores = SubScores(
            appearance=1,
            nose=8,
            palate=15,
            structure_balance=14,
            finish=7,
            typicity_complexity=10,
            overall_judgment=15,
        )
        expected = 1 + 8 + 15 + 14 + 7 + 10 + 15
        assert calculate_total_score(subscores) == expected
        assert calculate_total_score(subscores) == 70

    def test_deterministic_calculation(self) -> None:
        """Test that calculation is deterministic."""
        subscores = SubScores(
            appearance=2,
            nose=10,
            palate=18,
            structure_balance=17,
            finish=9,
            typicity_complexity=14,
            overall_judgment=18,
        )
        results = [calculate_total_score(subscores) for _ in range(10)]
        assert all(r == results[0] for r in results)
        assert results[0] == 88


class TestDetermineQualityBand:
    """Tests for determine_quality_band function."""

    def test_poor_band(self) -> None:
        """Test poor quality band (0-69)."""
        assert determine_quality_band(0) == QualityBand.POOR
        assert determine_quality_band(50) == QualityBand.POOR
        assert determine_quality_band(69) == QualityBand.POOR

    def test_acceptable_band(self) -> None:
        """Test acceptable quality band (70-79)."""
        assert determine_quality_band(70) == QualityBand.ACCEPTABLE
        assert determine_quality_band(75) == QualityBand.ACCEPTABLE
        assert determine_quality_band(79) == QualityBand.ACCEPTABLE

    def test_good_band(self) -> None:
        """Test good quality band (80-89)."""
        assert determine_quality_band(80) == QualityBand.GOOD
        assert determine_quality_band(85) == QualityBand.GOOD
        assert determine_quality_band(89) == QualityBand.GOOD

    def test_very_good_band(self) -> None:
        """Test very good quality band (90-94)."""
        assert determine_quality_band(90) == QualityBand.VERY_GOOD
        assert determine_quality_band(92) == QualityBand.VERY_GOOD
        assert determine_quality_band(94) == QualityBand.VERY_GOOD

    def test_outstanding_band(self) -> None:
        """Test outstanding quality band (95-100)."""
        assert determine_quality_band(95) == QualityBand.OUTSTANDING
        assert determine_quality_band(98) == QualityBand.OUTSTANDING
        assert determine_quality_band(100) == QualityBand.OUTSTANDING

    def test_boundary_values(self) -> None:
        """Test boundary values between bands."""
        assert determine_quality_band(69) == QualityBand.POOR
        assert determine_quality_band(70) == QualityBand.ACCEPTABLE
        assert determine_quality_band(79) == QualityBand.ACCEPTABLE
        assert determine_quality_band(80) == QualityBand.GOOD
        assert determine_quality_band(89) == QualityBand.GOOD
        assert determine_quality_band(90) == QualityBand.VERY_GOOD
        assert determine_quality_band(94) == QualityBand.VERY_GOOD
        assert determine_quality_band(95) == QualityBand.OUTSTANDING


class TestValidateAllSubscores:
    """Tests for validate_all_subscores function."""

    def test_valid_subscores(self) -> None:
        """Test validation passes for valid subscores."""
        subscores = SubScores(
            appearance=2,
            nose=10,
            palate=18,
            structure_balance=17,
            finish=9,
            typicity_complexity=14,
            overall_judgment=18,
        )
        errors = validate_all_subscores(subscores)
        assert errors == []

    def test_all_zeros_valid(self) -> None:
        """Test validation passes for all zeros."""
        subscores = SubScores()
        errors = validate_all_subscores(subscores)
        assert errors == []

    def test_max_values_valid(self) -> None:
        """Test validation passes for max values."""
        subscores = SubScores(
            appearance=2,
            nose=12,
            palate=20,
            structure_balance=20,
            finish=10,
            typicity_complexity=16,
            overall_judgment=20,
        )
        errors = validate_all_subscores(subscores)
        assert errors == []
