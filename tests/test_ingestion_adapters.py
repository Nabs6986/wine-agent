"""Tests for the ingestion adapters module."""

import json

import pytest

from wine_agent.ingestion.adapters import (
    ADAPTER_REGISTRY,
    get_adapter,
    get_adapter_info,
    list_adapters,
    register_adapter,
)
from wine_agent.ingestion.adapters.base import BaseAdapter, ExtractedField, ExtractedListing
from wine_agent.ingestion.adapters.test_adapter import TEST_WINES, TestAdapter


class TestAdapterRegistry:
    """Tests for the adapter registry functions."""

    def test_list_adapters(self) -> None:
        """Test listing available adapters."""
        adapters = list_adapters()
        assert "test" in adapters

    def test_get_adapter(self) -> None:
        """Test getting an adapter by name."""
        adapter = get_adapter("test")
        assert adapter is not None
        assert isinstance(adapter, TestAdapter)

    def test_get_adapter_not_found(self) -> None:
        """Test getting a non-existent adapter."""
        adapter = get_adapter("non-existent")
        assert adapter is None

    def test_get_adapter_with_config(self) -> None:
        """Test getting an adapter with custom config."""
        config = {"custom_option": "value"}
        adapter = get_adapter("test", config)
        assert adapter is not None
        assert adapter.config == config

    def test_get_adapter_info(self) -> None:
        """Test getting adapter information."""
        info = get_adapter_info("test")
        assert info is not None
        assert info["name"] == "test"
        assert info["version"] == "1.0.0"
        assert info["class"] == "TestAdapter"

    def test_get_adapter_info_not_found(self) -> None:
        """Test getting info for non-existent adapter."""
        info = get_adapter_info("non-existent")
        assert info is None


class TestExtractedField:
    """Tests for the ExtractedField class."""

    def test_valid_confidence(self) -> None:
        """Test creating with valid confidence."""
        field = ExtractedField("name", "value", 0.85, "css_selector")
        assert field.confidence == 0.85

    def test_invalid_confidence_low(self) -> None:
        """Test creating with confidence below 0."""
        with pytest.raises(ValueError):
            ExtractedField("name", "value", -0.1, "css_selector")

    def test_invalid_confidence_high(self) -> None:
        """Test creating with confidence above 1."""
        with pytest.raises(ValueError):
            ExtractedField("name", "value", 1.5, "css_selector")


class TestExtractedListing:
    """Tests for the ExtractedListing class."""

    def test_get_value(self) -> None:
        """Test getting field values."""
        listing = ExtractedListing(
            url="https://example.com",
            source_name="test",
            producer_name=ExtractedField("producer_name", "Test Producer", 0.9, "css"),
        )
        assert listing.get_value("producer_name") == "Test Producer"
        assert listing.get_value("wine_name") is None

    def test_get_confidence(self) -> None:
        """Test getting field confidence."""
        listing = ExtractedListing(
            url="https://example.com",
            source_name="test",
            producer_name=ExtractedField("producer_name", "Test Producer", 0.9, "css"),
        )
        assert listing.get_confidence("producer_name") == 0.9
        assert listing.get_confidence("wine_name") == 0.0

    def test_to_dict(self) -> None:
        """Test converting to dictionary."""
        listing = ExtractedListing(
            url="https://example.com",
            source_name="test",
            title="Test Wine",
            producer_name=ExtractedField("producer_name", "Test Producer", 0.9, "css"),
        )
        result = listing.to_dict()

        assert result["url"] == "https://example.com"
        assert result["source_name"] == "test"
        assert result["title"] == "Test Wine"
        assert result["producer_name"]["value"] == "Test Producer"
        assert result["producer_name"]["confidence"] == 0.9
        assert result["producer_name"]["method"] == "css"


class TestTestAdapter:
    """Tests for the TestAdapter class."""

    @pytest.fixture
    def adapter(self) -> TestAdapter:
        """Create a test adapter instance."""
        return TestAdapter()

    def test_adapter_info(self, adapter: TestAdapter) -> None:
        """Test adapter info."""
        info = adapter.get_info()
        assert info["name"] == "test"
        assert info["version"] == "1.0.0"

    def test_discover_urls(self, adapter: TestAdapter) -> None:
        """Test URL discovery."""
        urls = adapter.discover_urls()
        assert len(urls) == len(TEST_WINES)
        assert all(url.startswith("https://test.wineagent.local/wines/") for url in urls)

    def test_extract_listing_from_url(self, adapter: TestAdapter) -> None:
        """Test extracting listing by URL parsing."""
        url = "https://test.wineagent.local/wines/0"
        content = b"{}"  # Empty content, will fall back to URL parsing
        listing = adapter.extract_listing(content, url, "application/json")

        assert listing is not None
        assert listing.source_name == "test-wines"
        assert listing.get_value("producer_name") == "Domaine de la Romanée-Conti"

    def test_extract_listing_from_content(self, adapter: TestAdapter) -> None:
        """Test extracting listing from JSON content."""
        url = "https://test.wineagent.local/wines/1"
        content = json.dumps({"index": 1}).encode()
        listing = adapter.extract_listing(content, url, "application/json")

        assert listing is not None
        assert listing.get_value("producer_name") == "Château Margaux"

    def test_extract_listing_invalid_index(self, adapter: TestAdapter) -> None:
        """Test extracting listing with invalid index."""
        url = "https://test.wineagent.local/wines/999"
        content = b"{}"
        listing = adapter.extract_listing(content, url, "application/json")

        assert listing is None

    def test_extract_listing_all_fields(self, adapter: TestAdapter) -> None:
        """Test that all expected fields are extracted."""
        url = "https://test.wineagent.local/wines/0"
        content = adapter.get_test_content(0)
        listing = adapter.extract_listing(content, url, "application/json")

        assert listing is not None
        assert listing.get_value("producer_name") is not None
        assert listing.get_value("wine_name") is not None
        assert listing.get_value("region") is not None
        assert listing.get_value("country") is not None
        assert listing.get_value("grapes") is not None
        assert listing.get_value("color") is not None
        assert listing.get_value("abv") is not None
        assert listing.get_value("price") is not None

    def test_get_test_content(self, adapter: TestAdapter) -> None:
        """Test generating test content."""
        content = adapter.get_test_content(0)
        data = json.loads(content)
        assert data["index"] == 0

    def test_validate_listing(self, adapter: TestAdapter) -> None:
        """Test listing validation."""
        url = "https://test.wineagent.local/wines/0"
        content = adapter.get_test_content(0)
        listing = adapter.extract_listing(content, url, "application/json")

        errors = adapter.validate_listing(listing)
        assert errors == []  # Test data should be valid

    def test_custom_test_wines(self) -> None:
        """Test adapter with custom wine data."""
        custom_wines = [
            {
                "producer": "Custom Producer",
                "wine": "Custom Wine",
                "vintage": 2020,
                "region": "Custom Region",
                "country": "Custom Country",
                "grapes": ["Custom Grape"],
                "color": "red",
                "style": "still",
                "abv": 13.0,
                "bottle_size_ml": 750,
                "price": 50.00,
                "currency": "USD",
                "in_stock": True,
                "description": "Custom description",
            }
        ]
        adapter = TestAdapter(config={"test_wines": custom_wines})

        urls = adapter.discover_urls()
        assert len(urls) == 1

        listing = adapter.extract_listing(
            adapter.get_test_content(0),
            urls[0],
            "application/json",
        )
        assert listing.get_value("producer_name") == "Custom Producer"


class TestBaseAdapter:
    """Tests for BaseAdapter validation."""

    def test_validate_missing_title(self) -> None:
        """Test validation fails for missing title/wine name."""
        listing = ExtractedListing(
            url="https://example.com",
            source_name="test",
        )
        adapter = TestAdapter()
        errors = adapter.validate_listing(listing)
        assert "Missing title or wine name" in errors

    def test_validate_invalid_vintage(self) -> None:
        """Test validation fails for invalid vintage."""
        listing = ExtractedListing(
            url="https://example.com",
            source_name="test",
            title="Test Wine",
            vintage_year=ExtractedField("vintage_year", 1500, 1.0, "manual"),
        )
        adapter = TestAdapter()
        errors = adapter.validate_listing(listing)
        assert any("vintage" in e.lower() for e in errors)

    def test_validate_suspicious_abv(self) -> None:
        """Test validation warns for suspicious ABV."""
        listing = ExtractedListing(
            url="https://example.com",
            source_name="test",
            title="Test Wine",
            abv=ExtractedField("abv", 50.0, 1.0, "manual"),
        )
        adapter = TestAdapter()
        errors = adapter.validate_listing(listing)
        assert any("abv" in e.lower() for e in errors)

    def test_validate_invalid_price(self) -> None:
        """Test validation fails for invalid price."""
        listing = ExtractedListing(
            url="https://example.com",
            source_name="test",
            title="Test Wine",
            price=ExtractedField("price", -10.0, 1.0, "manual"),
        )
        adapter = TestAdapter()
        errors = adapter.validate_listing(listing)
        assert any("price" in e.lower() for e in errors)
