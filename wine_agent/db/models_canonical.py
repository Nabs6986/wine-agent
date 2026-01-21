"""SQLAlchemy ORM models for Wine Agent canonical entities.

These models define the database tables for the canonical wine catalog:
- ProducerDB, WineDB, VintageDB (core wine entities)
- RegionDB, GrapeVarietyDB (reference entities)
- ImporterDB, DistributorDB (trade entities)
- SourceDB, SnapshotDB, ListingDB, ListingMatchDB (ingestion entities)
- FieldProvenanceDB (provenance tracking)
"""

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from wine_agent.db.models import Base


def _utc_now() -> datetime:
    """Return current UTC datetime (timezone-aware)."""
    return datetime.now(UTC)


def _generate_uuid() -> str:
    """Generate a UUID string."""
    return str(uuid4())


# ============================================================================
# Core Wine Entities
# ============================================================================


class ProducerDB(Base):
    """
    Database model for canonical wine producers.

    Represents a winery, domaine, or producer of wines.
    """

    __tablename__ = "producers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_generate_uuid)
    canonical_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    aliases_json: Mapped[str] = mapped_column(Text, default="[]")  # JSON array
    country: Mapped[str] = mapped_column(String(100), default="", index=True)
    region: Mapped[str] = mapped_column(String(100), default="", index=True)
    website: Mapped[str] = mapped_column(String(500), default="")
    wikidata_id: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now, onupdate=_utc_now)

    # Relationships
    wines: Mapped[list["WineDB"]] = relationship("WineDB", back_populates="producer")

    def __repr__(self) -> str:
        return f"<ProducerDB(id={self.id}, name='{self.canonical_name}')>"


class WineDB(Base):
    """
    Database model for canonical wines (cuvée/product line).

    Represents a wine product independent of vintage year.
    """

    __tablename__ = "wines"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_generate_uuid)
    producer_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("producers.id"), nullable=False, index=True
    )
    canonical_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    aliases_json: Mapped[str] = mapped_column(Text, default="[]")  # JSON array
    color: Mapped[str | None] = mapped_column(String(20), nullable=True)
    style: Mapped[str | None] = mapped_column(String(20), nullable=True)
    grapes_json: Mapped[str] = mapped_column(Text, default="[]")  # JSON array
    appellation: Mapped[str] = mapped_column(String(255), default="", index=True)
    region_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("regions.id"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now, onupdate=_utc_now)

    # Relationships
    producer: Mapped["ProducerDB"] = relationship("ProducerDB", back_populates="wines")
    region: Mapped["RegionDB | None"] = relationship("RegionDB", back_populates="wines")
    vintages: Mapped[list["VintageDB"]] = relationship("VintageDB", back_populates="wine")

    def __repr__(self) -> str:
        return f"<WineDB(id={self.id}, name='{self.canonical_name}')>"


class VintageDB(Base):
    """
    Database model for canonical wine vintages.

    Represents a specific year/release of a wine.
    """

    __tablename__ = "vintages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_generate_uuid)
    wine_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("wines.id"), nullable=False, index=True
    )
    year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    bottle_size_ml: Mapped[int] = mapped_column(Integer, default=750)
    abv: Mapped[float | None] = mapped_column(Float, nullable=True)
    tech_sheet_attrs_json: Mapped[str] = mapped_column(Text, default="{}")  # JSON object
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now, onupdate=_utc_now)

    # Relationships
    wine: Mapped["WineDB"] = relationship("WineDB", back_populates="vintages")

    def __repr__(self) -> str:
        return f"<VintageDB(id={self.id}, wine_id={self.wine_id}, year={self.year})>"


# ============================================================================
# Reference Entities
# ============================================================================


class RegionDB(Base):
    """
    Database model for canonical wine regions.

    Supports hierarchical structure from country to vineyard level.
    """

    __tablename__ = "regions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_generate_uuid)
    parent_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("regions.id"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    aliases_json: Mapped[str] = mapped_column(Text, default="[]")  # JSON array
    country: Mapped[str] = mapped_column(String(100), default="", index=True)
    wikidata_id: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    hierarchy_level: Mapped[str] = mapped_column(String(20), default="region")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now, onupdate=_utc_now)

    # Relationships
    parent: Mapped["RegionDB | None"] = relationship(
        "RegionDB", remote_side="RegionDB.id", back_populates="children"
    )
    children: Mapped[list["RegionDB"]] = relationship("RegionDB", back_populates="parent")
    wines: Mapped[list["WineDB"]] = relationship("WineDB", back_populates="region")

    def __repr__(self) -> str:
        return f"<RegionDB(id={self.id}, name='{self.name}')>"


class GrapeVarietyDB(Base):
    """
    Database model for canonical grape varieties.

    Includes aliases for matching different spellings/names.
    """

    __tablename__ = "grape_varieties"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_generate_uuid)
    canonical_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    aliases_json: Mapped[str] = mapped_column(Text, default="[]")  # JSON array
    wikidata_id: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now, onupdate=_utc_now)

    def __repr__(self) -> str:
        return f"<GrapeVarietyDB(id={self.id}, name='{self.canonical_name}')>"


# ============================================================================
# Trade Entities
# ============================================================================


class ImporterDB(Base):
    """
    Database model for wine importers.

    Represents companies that import wines into a market.
    """

    __tablename__ = "importers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_generate_uuid)
    canonical_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    country: Mapped[str] = mapped_column(String(100), default="", index=True)
    website: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now, onupdate=_utc_now)

    def __repr__(self) -> str:
        return f"<ImporterDB(id={self.id}, name='{self.canonical_name}')>"


class DistributorDB(Base):
    """
    Database model for wine distributors.

    Represents companies that distribute wines within a market.
    """

    __tablename__ = "distributors"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_generate_uuid)
    canonical_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    country: Mapped[str] = mapped_column(String(100), default="", index=True)
    website: Mapped[str] = mapped_column(String(500), default="")
    regions_served_json: Mapped[str] = mapped_column(Text, default="[]")  # JSON array
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now, onupdate=_utc_now)

    def __repr__(self) -> str:
        return f"<DistributorDB(id={self.id}, name='{self.canonical_name}')>"


# ============================================================================
# Ingestion Entities
# ============================================================================


class SourceDB(Base):
    """
    Database model for data source configurations.

    Defines crawl rules, rate limits, and adapter settings for a domain.
    """

    __tablename__ = "sources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_generate_uuid)
    domain: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    adapter_type: Mapped[str] = mapped_column(String(50), nullable=False)
    rate_limit_config_json: Mapped[str] = mapped_column(
        Text, default='{"requests_per_second": 1.0, "burst_limit": 5}'
    )
    allowlist_json: Mapped[str] = mapped_column(Text, default="[]")  # JSON array
    denylist_json: Mapped[str] = mapped_column(Text, default="[]")  # JSON array
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now, onupdate=_utc_now)

    # Relationships
    snapshots: Mapped[list["SnapshotDB"]] = relationship("SnapshotDB", back_populates="source")
    listings: Mapped[list["ListingDB"]] = relationship("ListingDB", back_populates="source")

    def __repr__(self) -> str:
        return f"<SourceDB(id={self.id}, domain='{self.domain}')>"


class SnapshotDB(Base):
    """
    Database model for raw content snapshots.

    Stores fetched content metadata for reprocessing.
    """

    __tablename__ = "snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_generate_uuid)
    source_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("sources.id"), nullable=False, index=True
    )
    url: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    mime_type: Mapped[str] = mapped_column(String(100), default="text/html")
    file_path: Mapped[str] = mapped_column(Text, default="")
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now, index=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending/success/failed/duplicate

    # Relationships
    source: Mapped["SourceDB"] = relationship("SourceDB", back_populates="snapshots")
    listings: Mapped[list["ListingDB"]] = relationship("ListingDB", back_populates="snapshot")

    def __repr__(self) -> str:
        return f"<SnapshotDB(id={self.id}, status='{self.status}')>"


class ListingDB(Base):
    """
    Database model for parsed listings.

    Contains extracted data from a retailer or catalog page.
    """

    __tablename__ = "listings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_generate_uuid)
    source_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("sources.id"), nullable=False, index=True
    )
    snapshot_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("snapshots.id"), nullable=False, index=True
    )
    url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(String(500), default="")
    sku: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    upc: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    ean: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    price: Mapped[float | None] = mapped_column(Float, nullable=True)
    currency: Mapped[str] = mapped_column(String(10), default="USD")
    parsed_fields_json: Mapped[str] = mapped_column(Text, default="{}")  # JSON object
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now, index=True)

    # Relationships
    source: Mapped["SourceDB"] = relationship("SourceDB", back_populates="listings")
    snapshot: Mapped["SnapshotDB"] = relationship("SnapshotDB", back_populates="listings")
    matches: Mapped[list["ListingMatchDB"]] = relationship("ListingMatchDB", back_populates="listing")

    def __repr__(self) -> str:
        return f"<ListingDB(id={self.id}, title='{self.title[:30]}...')>"


class ListingMatchDB(Base):
    """
    Database model for listing-to-entity matches.

    Tracks confidence and decision type for entity resolution.
    """

    __tablename__ = "listing_matches"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_generate_uuid)
    listing_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("listings.id"), nullable=False, index=True
    )
    entity_type: Mapped[str] = mapped_column(String(20), nullable=False)  # producer/wine/vintage/etc.
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    decision: Mapped[str] = mapped_column(String(20), default="auto")  # auto/manual/rejected
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)

    # Relationships
    listing: Mapped["ListingDB"] = relationship("ListingDB", back_populates="matches")

    def __repr__(self) -> str:
        return f"<ListingMatchDB(id={self.id}, entity_type='{self.entity_type}', confidence={self.confidence})>"


# ============================================================================
# Provenance Tracking
# ============================================================================


class FieldProvenanceDB(Base):
    """
    Database model for field-level provenance tracking.

    Tracks the source, confidence, and extraction details for any
    canonical entity field value.
    """

    __tablename__ = "field_provenance"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_generate_uuid)
    entity_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    field_path: Mapped[str] = mapped_column(String(100), nullable=False)
    value_json: Mapped[str] = mapped_column(Text, nullable=False)  # JSON-encoded value
    source_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("sources.id"), nullable=False, index=True
    )
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    extractor_version: Mapped[str] = mapped_column(String(20), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    snapshot_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("snapshots.id"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)

    def __repr__(self) -> str:
        return f"<FieldProvenanceDB(entity={self.entity_type}:{self.entity_id}, field='{self.field_path}')>"
