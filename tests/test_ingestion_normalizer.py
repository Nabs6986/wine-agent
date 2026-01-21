"""Tests for the ingestion normalizer module."""

import pytest

from wine_agent.ingestion.adapters.base import ExtractedField, ExtractedListing
from wine_agent.ingestion.normalizer import NormalizedListing, Normalizer


class TestNormalizer:
    """Tests for the Normalizer class."""

    @pytest.fixture
    def normalizer(self) -> Normalizer:
        """Create a normalizer instance."""
        return Normalizer()

    def test_normalize_region_aliases(self, normalizer: Normalizer) -> None:
        """Test region name normalization with aliases."""
        # Test common aliases
        assert normalizer.normalize_region("burgundy") == "Bourgogne"
        assert normalizer.normalize_region("Burgundy") == "Bourgogne"
        assert normalizer.normalize_region("BURGUNDY") == "Bourgogne"
        assert normalizer.normalize_region("napa valley") == "Napa Valley"
        assert normalizer.normalize_region("barossa") == "Barossa Valley"
        assert normalizer.normalize_region("champagne") == "Champagne"

    def test_normalize_region_no_alias(self, normalizer: Normalizer) -> None:
        """Test that unknown regions are returned as-is."""
        assert normalizer.normalize_region("Some Unknown Region") == "Some Unknown Region"
        assert normalizer.normalize_region(None) is None

    def test_normalize_grapes_from_list(self, normalizer: Normalizer) -> None:
        """Test grape normalization from list input."""
        grapes = ["cab", "merlot", "Pinot Noir"]
        normalized = normalizer.normalize_grapes(grapes)
        assert normalized == ["Cabernet Sauvignon", "Merlot", "Pinot Noir"]

    def test_normalize_grapes_from_string(self, normalizer: Normalizer) -> None:
        """Test grape normalization from comma-separated string."""
        grapes = "cab, merlot, shiraz"
        normalized = normalizer.normalize_grapes(grapes)
        assert normalized == ["Cabernet Sauvignon", "Merlot", "Shiraz"]

    def test_normalize_grapes_with_and(self, normalizer: Normalizer) -> None:
        """Test grape normalization with 'and' separator."""
        grapes = "Chardonnay and Sauvignon Blanc"
        normalized = normalizer.normalize_grapes(grapes)
        assert "Chardonnay" in normalized
        assert "Sauvignon Blanc" in normalized

    def test_normalize_grapes_none(self, normalizer: Normalizer) -> None:
        """Test grape normalization with None input."""
        assert normalizer.normalize_grapes(None) == []

    def test_parse_abv_float(self, normalizer: Normalizer) -> None:
        """Test ABV parsing from float."""
        assert normalizer.parse_abv(13.5) == 13.5
        assert normalizer.parse_abv(14) == 14.0

    def test_parse_abv_string(self, normalizer: Normalizer) -> None:
        """Test ABV parsing from string."""
        assert normalizer.parse_abv("13.5%") == 13.5
        assert normalizer.parse_abv("13.5% abv") == 13.5
        assert normalizer.parse_abv("ABV: 14%") == 14.0
        assert normalizer.parse_abv("Alcohol: 12.5%") == 12.5

    def test_parse_abv_invalid(self, normalizer: Normalizer) -> None:
        """Test ABV parsing with invalid input."""
        assert normalizer.parse_abv(None) is None
        assert normalizer.parse_abv("not a number") is None
        assert normalizer.parse_abv(50) is None  # Out of range

    def test_parse_vintage_int(self, normalizer: Normalizer) -> None:
        """Test vintage parsing from int."""
        assert normalizer.parse_vintage(2019) == 2019
        assert normalizer.parse_vintage(2023) == 2023

    def test_parse_vintage_string(self, normalizer: Normalizer) -> None:
        """Test vintage parsing from string."""
        assert normalizer.parse_vintage("2019") == 2019
        assert normalizer.parse_vintage("Vintage 2020") == 2020

    def test_parse_vintage_nv(self, normalizer: Normalizer) -> None:
        """Test vintage parsing for non-vintage wines."""
        assert normalizer.parse_vintage("NV") is None
        assert normalizer.parse_vintage("N/V") is None
        assert normalizer.parse_vintage("Non-Vintage") is None

    def test_parse_vintage_invalid(self, normalizer: Normalizer) -> None:
        """Test vintage parsing with invalid input."""
        assert normalizer.parse_vintage(None) is None
        assert normalizer.parse_vintage("not a year") is None
        assert normalizer.parse_vintage(1500) is None  # Out of range

    def test_normalize_listing_full(self, normalizer: Normalizer) -> None:
        """Test full listing normalization."""
        extracted = ExtractedListing(
            url="https://example.com/wine/1",
            source_name="test",
            title="Test Wine 2019",
            producer_name=ExtractedField("producer_name", "Test Producer", 0.9, "css"),
            wine_name=ExtractedField("wine_name", "Grand Cru", 0.9, "css"),
            vintage_year=ExtractedField("vintage_year", "2019", 0.9, "css"),
            region=ExtractedField("region", "burgundy", 0.9, "css"),
            country=ExtractedField("country", "France", 0.9, "css"),
            grapes=ExtractedField("grapes", ["pinot"], 0.9, "css"),
            color=ExtractedField("color", "red", 0.9, "css"),
            abv=ExtractedField("abv", "13.5%", 0.9, "css"),
            price=ExtractedField("price", 99.99, 0.9, "css"),
            currency=ExtractedField("currency", "usd", 0.9, "css"),
        )

        normalized = normalizer.normalize_listing(extracted)

        assert normalized.producer_name == "Test Producer"
        assert normalized.wine_name == "Grand Cru"
        assert normalized.vintage_year == 2019
        assert normalized.region == "Bourgogne"  # Normalized from "burgundy"
        assert normalized.country == "France"
        assert normalized.grapes == ["Pinot Noir"]  # Normalized from "pinot"
        assert normalized.color == "red"
        assert normalized.abv == 13.5
        assert normalized.price == 99.99
        assert normalized.currency == "USD"

    def test_normalize_listing_missing_fields(self, normalizer: Normalizer) -> None:
        """Test listing normalization with missing fields."""
        extracted = ExtractedListing(
            url="https://example.com/wine/1",
            source_name="test",
            title="Test Wine",
        )

        normalized = normalizer.normalize_listing(extracted)

        assert normalized.producer_name is None
        assert normalized.wine_name is None
        assert normalized.vintage_year is None
        assert normalized.grapes == []
        assert normalized.bottle_size_ml == 750  # Default

    def test_parse_bottle_size(self, normalizer: Normalizer) -> None:
        """Test bottle size parsing."""
        # Test via _parse_bottle_size method
        assert normalizer._parse_bottle_size("750ml") == 750
        assert normalizer._parse_bottle_size("750 ml") == 750
        assert normalizer._parse_bottle_size("375ml") == 375
        assert normalizer._parse_bottle_size("1.5L") == 1500
        assert normalizer._parse_bottle_size("1.5 liter") == 1500
        assert normalizer._parse_bottle_size("Magnum") == 1500
        assert normalizer._parse_bottle_size("half bottle") == 375
        assert normalizer._parse_bottle_size("unknown") == 750  # Default


class TestNormalizedListing:
    """Tests for the NormalizedListing dataclass."""

    def test_default_values(self) -> None:
        """Test default values."""
        listing = NormalizedListing()
        assert listing.bottle_size_ml == 750
        assert listing.grapes == []
        assert listing.url == ""

    def test_with_values(self) -> None:
        """Test with provided values."""
        listing = NormalizedListing(
            producer_name="Test Producer",
            wine_name="Test Wine",
            vintage_year=2019,
            region="Burgundy",
            grapes=["Pinot Noir"],
        )
        assert listing.producer_name == "Test Producer"
        assert listing.vintage_year == 2019
        assert listing.grapes == ["Pinot Noir"]
