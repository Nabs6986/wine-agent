"""Canonical Pydantic v2 models for Wine Agent entity catalog.

These models define the canonical wine catalog entities:
- Producer, Wine, Vintage (core wine entities)
- Region, GrapeVariety (reference entities)
- Importer, Distributor (trade entities)
- Source, Snapshot, Listing, ListingMatch (ingestion entities)
- FieldProvenance (provenance tracking)
"""

from datetime import UTC, datetime
from enum import Enum
from typing import Annotated
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator

from wine_agent.core.enums import WineColor, WineStyle


def _utc_now() -> datetime:
    """Return current UTC datetime (timezone-aware)."""
    return datetime.now(UTC)


# ============================================================================
# Enums for Canonical Entities
# ============================================================================


class MatchDecision(str, Enum):
    """Decision type for listing matches."""

    AUTO = "auto"
    MANUAL = "manual"
    REJECTED = "rejected"


class SnapshotStatus(str, Enum):
    """Status of a fetched snapshot."""

    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    DUPLICATE = "duplicate"


class EntityType(str, Enum):
    """Types of canonical entities for matching."""

    PRODUCER = "producer"
    WINE = "wine"
    VINTAGE = "vintage"
    REGION = "region"
    GRAPE = "grape"
    IMPORTER = "importer"
    DISTRIBUTOR = "distributor"


class RegionHierarchyLevel(str, Enum):
    """Hierarchy levels for wine regions."""

    COUNTRY = "country"
    REGION = "region"
    SUBREGION = "subregion"
    APPELLATION = "appellation"
    VINEYARD = "vineyard"


# ============================================================================
# Core Wine Entities
# ============================================================================


class Producer(BaseModel):
    """
    Canonical wine producer entity.

    Represents a winery, domaine, or producer of wines.
    """

    id: UUID = Field(default_factory=uuid4)
    canonical_name: str
    aliases: list[str] = Field(default_factory=list)
    country: str = ""
    region: str = ""
    website: str = ""
    wikidata_id: str | None = None
    created_at: datetime = Field(default_factory=_utc_now)
    updated_at: datetime = Field(default_factory=_utc_now)

    @field_validator("canonical_name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("canonical_name cannot be empty")
        return v.strip()


class Wine(BaseModel):
    """
    Canonical wine entity (a cuvée/product line).

    Represents a wine product independent of vintage year.
    Links to a producer and optionally to a region.
    """

    id: UUID = Field(default_factory=uuid4)
    producer_id: UUID
    canonical_name: str
    aliases: list[str] = Field(default_factory=list)
    color: WineColor | None = None
    style: WineStyle | None = None
    grapes: list[str] = Field(default_factory=list)
    appellation: str = ""
    region_id: UUID | None = None
    created_at: datetime = Field(default_factory=_utc_now)
    updated_at: datetime = Field(default_factory=_utc_now)

    @field_validator("canonical_name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("canonical_name cannot be empty")
        return v.strip()


class Vintage(BaseModel):
    """
    Canonical vintage entity.

    Represents a specific year/release of a wine.
    Contains vintage-specific attributes like ABV, bottle size, etc.
    """

    id: UUID = Field(default_factory=uuid4)
    wine_id: UUID
    year: int
    bottle_size_ml: int = 750
    abv: float | None = None
    tech_sheet_attrs: dict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=_utc_now)
    updated_at: datetime = Field(default_factory=_utc_now)

    @field_validator("year")
    @classmethod
    def valid_year(cls, v: int) -> int:
        if v < 1800 or v > 2100:
            raise ValueError("year must be between 1800 and 2100")
        return v


# ============================================================================
# Reference Entities
# ============================================================================


class Region(BaseModel):
    """
    Canonical wine region entity with hierarchical structure.

    Supports hierarchy from country down to vineyard level.
    """

    id: UUID = Field(default_factory=uuid4)
    parent_id: UUID | None = None
    name: str
    aliases: list[str] = Field(default_factory=list)
    country: str = ""
    wikidata_id: str | None = None
    hierarchy_level: RegionHierarchyLevel = RegionHierarchyLevel.REGION
    created_at: datetime = Field(default_factory=_utc_now)
    updated_at: datetime = Field(default_factory=_utc_now)

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("name cannot be empty")
        return v.strip()


class GrapeVariety(BaseModel):
    """
    Canonical grape variety entity.

    Includes aliases for matching different spellings/names.
    """

    id: UUID = Field(default_factory=uuid4)
    canonical_name: str
    aliases: list[str] = Field(default_factory=list)
    wikidata_id: str | None = None
    created_at: datetime = Field(default_factory=_utc_now)
    updated_at: datetime = Field(default_factory=_utc_now)

    @field_validator("canonical_name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("canonical_name cannot be empty")
        return v.strip()


# ============================================================================
# Trade Entities
# ============================================================================


class Importer(BaseModel):
    """
    Wine importer entity.

    Represents companies that import wines into a market.
    """

    id: UUID = Field(default_factory=uuid4)
    canonical_name: str
    country: str = ""
    website: str = ""
    created_at: datetime = Field(default_factory=_utc_now)
    updated_at: datetime = Field(default_factory=_utc_now)

    @field_validator("canonical_name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("canonical_name cannot be empty")
        return v.strip()


class Distributor(BaseModel):
    """
    Wine distributor entity.

    Represents companies that distribute wines within a market.
    """

    id: UUID = Field(default_factory=uuid4)
    canonical_name: str
    country: str = ""
    website: str = ""
    regions_served: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=_utc_now)
    updated_at: datetime = Field(default_factory=_utc_now)

    @field_validator("canonical_name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("canonical_name cannot be empty")
        return v.strip()


# ============================================================================
# Ingestion Entities
# ============================================================================


class Source(BaseModel):
    """
    Data source configuration for ingestion.

    Defines crawl rules, rate limits, and adapter settings for a domain.
    """

    id: UUID = Field(default_factory=uuid4)
    domain: str
    adapter_type: str
    rate_limit_config: dict = Field(default_factory=lambda: {
        "requests_per_second": 1.0,
        "burst_limit": 5,
    })
    allowlist: list[str] = Field(default_factory=list)
    denylist: list[str] = Field(default_factory=list)
    enabled: bool = True
    created_at: datetime = Field(default_factory=_utc_now)
    updated_at: datetime = Field(default_factory=_utc_now)

    @field_validator("domain")
    @classmethod
    def domain_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("domain cannot be empty")
        return v.strip().lower()


class Snapshot(BaseModel):
    """
    Raw content snapshot from a source.

    Stores the fetched content with metadata for reprocessing.
    """

    id: UUID = Field(default_factory=uuid4)
    source_id: UUID
    url: str
    content_hash: str
    mime_type: str = "text/html"
    file_path: str = ""
    fetched_at: datetime = Field(default_factory=_utc_now)
    status: SnapshotStatus = SnapshotStatus.PENDING

    @field_validator("url")
    @classmethod
    def url_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("url cannot be empty")
        return v.strip()


class Listing(BaseModel):
    """
    Parsed listing from a source.

    Contains extracted data from a retailer or catalog page.
    """

    id: UUID = Field(default_factory=uuid4)
    source_id: UUID
    snapshot_id: UUID
    url: str
    title: str = ""
    sku: str | None = None
    upc: str | None = None
    ean: str | None = None
    price: float | None = None
    currency: str = "USD"
    parsed_fields: dict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=_utc_now)


class ListingMatch(BaseModel):
    """
    Match between a listing and a canonical entity.

    Tracks the confidence and decision type for entity resolution.
    """

    id: UUID = Field(default_factory=uuid4)
    listing_id: UUID
    entity_type: EntityType
    entity_id: UUID
    confidence: Annotated[float, Field(ge=0.0, le=1.0)]
    decision: MatchDecision = MatchDecision.AUTO
    created_at: datetime = Field(default_factory=_utc_now)


# ============================================================================
# Provenance Tracking
# ============================================================================


class FieldProvenance(BaseModel):
    """
    Provenance record for a single field value.

    Tracks the source, confidence, and extraction details for any
    canonical entity field value.
    """

    id: UUID = Field(default_factory=uuid4)
    entity_type: EntityType
    entity_id: UUID
    field_path: str  # e.g., "vintage.abv", "wine.grapes[0]"
    value: str | int | float | bool | list | dict | None
    source_id: UUID
    source_url: str
    fetched_at: datetime
    extractor_version: str
    confidence: Annotated[float, Field(ge=0.0, le=1.0)]
    snapshot_id: UUID | None = None
    created_at: datetime = Field(default_factory=_utc_now)

    @field_validator("field_path")
    @classmethod
    def field_path_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("field_path cannot be empty")
        return v.strip()


# ============================================================================
# Search/API Models
# ============================================================================


class CatalogSearchResult(BaseModel):
    """Search result for canonical wine catalog."""

    vintage: Vintage | None = None
    wine: Wine
    producer: Producer
    region: Region | None = None
    source_count: int = 0


class CatalogSearchRequest(BaseModel):
    """Request parameters for catalog search."""

    query: str = ""
    producer: str | None = None
    wine_name: str | None = None
    vintage_year: int | None = None
    region: str | None = None
    country: str | None = None
    grape: str | None = None
    upc: str | None = None
    ean: str | None = None
    page: int = 1
    page_size: int = 20


class CatalogStats(BaseModel):
    """Statistics about the canonical catalog."""

    total_producers: int = 0
    total_wines: int = 0
    total_vintages: int = 0
    total_regions: int = 0
    total_grapes: int = 0
    total_sources: int = 0
    total_listings: int = 0
    last_updated: datetime | None = None
