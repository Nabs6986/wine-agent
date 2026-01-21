"""
Adapter Base Module
===================

Defines the abstract base class for source-specific adapters.
Adapters are responsible for:
1. Discovering URLs to crawl from a source
2. Extracting structured wine data from HTML/JSON content
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any


@dataclass
class ExtractedField:
    """
    A field extracted from source content with confidence metadata.

    Tracks how the field was extracted for debugging and quality assessment.
    """

    field_name: str
    value: Any
    confidence: float  # 0.0 - 1.0
    extractor_method: str  # "jsonld", "css_selector", "regex", "meta_tag", "manual"

    def __post_init__(self) -> None:
        """Validate confidence is in range."""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"Confidence must be between 0.0 and 1.0, got {self.confidence}")


@dataclass
class ExtractedListing:
    """
    Structured wine listing extracted from a source page.

    Contains all fields that can be extracted from a wine product page,
    along with extraction confidence scores.
    """

    # Source information
    url: str
    source_name: str

    # Wine identity
    title: str | None = None
    producer_name: ExtractedField | None = None
    wine_name: ExtractedField | None = None
    vintage_year: ExtractedField | None = None

    # Wine characteristics
    region: ExtractedField | None = None
    sub_region: ExtractedField | None = None
    appellation: ExtractedField | None = None
    country: ExtractedField | None = None
    grapes: ExtractedField | None = None  # list[str] or comma-separated string
    color: ExtractedField | None = None  # red, white, rosé, etc.
    style: ExtractedField | None = None  # still, sparkling, fortified

    # Technical details
    abv: ExtractedField | None = None  # Alcohol by volume (percentage)
    bottle_size_ml: ExtractedField | None = None  # Bottle size in ml

    # Pricing
    price: ExtractedField | None = None  # Decimal price
    currency: ExtractedField | None = None  # ISO currency code (USD, EUR, etc.)
    price_per_bottle: ExtractedField | None = None

    # Availability
    in_stock: ExtractedField | None = None  # bool
    quantity_available: ExtractedField | None = None  # int

    # Scores and reviews
    critic_scores: ExtractedField | None = None  # list of dicts with source, score
    description: ExtractedField | None = None
    tasting_notes: ExtractedField | None = None

    # Identifiers
    sku: ExtractedField | None = None
    upc: ExtractedField | None = None

    # Raw data for debugging
    raw_jsonld: dict[str, Any] | None = None
    extraction_errors: list[str] = field(default_factory=list)

    def get_value(self, field_name: str) -> Any | None:
        """
        Get the raw value of an extracted field.

        Args:
            field_name: Name of the field

        Returns:
            The field value, or None if not extracted
        """
        field_obj = getattr(self, field_name, None)
        if isinstance(field_obj, ExtractedField):
            return field_obj.value
        return field_obj

    def get_confidence(self, field_name: str) -> float:
        """
        Get the extraction confidence for a field.

        Args:
            field_name: Name of the field

        Returns:
            Confidence score (0.0-1.0), or 0.0 if not extracted
        """
        field_obj = getattr(self, field_name, None)
        if isinstance(field_obj, ExtractedField):
            return field_obj.confidence
        return 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        result: dict[str, Any] = {
            "url": self.url,
            "source_name": self.source_name,
            "title": self.title,
            "extraction_errors": self.extraction_errors,
        }

        # Add extracted fields with their metadata
        field_names = [
            "producer_name", "wine_name", "vintage_year", "region", "sub_region",
            "appellation", "country", "grapes", "color", "style", "abv",
            "bottle_size_ml", "price", "currency", "price_per_bottle",
            "in_stock", "quantity_available", "critic_scores", "description",
            "tasting_notes", "sku", "upc",
        ]

        for field_name in field_names:
            field_obj = getattr(self, field_name, None)
            if field_obj is not None:
                if isinstance(field_obj, ExtractedField):
                    result[field_name] = {
                        "value": field_obj.value,
                        "confidence": field_obj.confidence,
                        "method": field_obj.extractor_method,
                    }
                else:
                    result[field_name] = field_obj

        return result


class BaseAdapter(ABC):
    """
    Abstract base class for source-specific adapters.

    Subclasses must implement:
    - discover_urls: Find URLs to crawl from the source
    - extract_listing: Parse content and extract wine data
    """

    # Adapter identification (override in subclasses)
    ADAPTER_NAME: str = "base"
    ADAPTER_VERSION: str = "1.0.0"

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        """
        Initialize the adapter.

        Args:
            config: Optional custom configuration from sources.yaml
        """
        self.config = config or {}

    @abstractmethod
    def discover_urls(self, seed_urls: list[str] | None = None) -> list[str]:
        """
        Discover URLs to crawl from this source.

        This method should return a list of product page URLs that
        can be passed to extract_listing.

        Args:
            seed_urls: Optional starting URLs for discovery

        Returns:
            List of URLs to crawl
        """
        pass

    @abstractmethod
    def extract_listing(
        self,
        content: bytes,
        url: str,
        mime_type: str,
    ) -> ExtractedListing | None:
        """
        Extract wine listing data from page content.

        Args:
            content: Raw page content (HTML, JSON, etc.)
            url: URL the content was fetched from
            mime_type: Content MIME type

        Returns:
            ExtractedListing with structured data, or None if extraction failed
        """
        pass

    def validate_listing(self, listing: ExtractedListing) -> list[str]:
        """
        Validate an extracted listing.

        Override this method to add adapter-specific validation.

        Args:
            listing: Extracted listing to validate

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        # Must have at least a title or wine name
        if not listing.title and not listing.get_value("wine_name"):
            errors.append("Missing title or wine name")

        # Vintage year must be reasonable if present
        vintage = listing.get_value("vintage_year")
        if vintage is not None:
            try:
                year = int(vintage)
                if year < 1800 or year > 2100:
                    errors.append(f"Invalid vintage year: {vintage}")
            except (TypeError, ValueError):
                errors.append(f"Invalid vintage year format: {vintage}")

        # ABV must be reasonable if present
        abv = listing.get_value("abv")
        if abv is not None:
            try:
                abv_val = float(abv)
                if abv_val < 0 or abv_val > 25:
                    errors.append(f"Suspicious ABV value: {abv}")
            except (TypeError, ValueError):
                errors.append(f"Invalid ABV format: {abv}")

        # Price must be positive if present
        price = listing.get_value("price")
        if price is not None:
            try:
                price_val = Decimal(str(price))
                if price_val <= 0:
                    errors.append(f"Invalid price: {price}")
            except Exception:
                errors.append(f"Invalid price format: {price}")

        return errors

    def get_info(self) -> dict[str, str]:
        """Get adapter information."""
        return {
            "name": self.ADAPTER_NAME,
            "version": self.ADAPTER_VERSION,
            "class": self.__class__.__name__,
        }
