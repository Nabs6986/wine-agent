"""Repository classes for canonical entity database operations."""

import json
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from wine_agent.core.schema_canonical import (
    Distributor,
    FieldProvenance,
    GrapeVariety,
    Importer,
    Listing,
    ListingMatch,
    Producer,
    Region,
    Snapshot,
    Source,
    Vintage,
    Wine,
)
from wine_agent.db.models_canonical import (
    DistributorDB,
    FieldProvenanceDB,
    GrapeVarietyDB,
    ImporterDB,
    ListingDB,
    ListingMatchDB,
    ProducerDB,
    RegionDB,
    SnapshotDB,
    SourceDB,
    VintageDB,
    WineDB,
)


def _utc_now() -> datetime:
    """Return current UTC datetime."""
    return datetime.now(UTC)


# ============================================================================
# Core Wine Entity Repositories
# ============================================================================


class ProducerRepository:
    """Repository for Producer CRUD operations."""

    def __init__(self, session: Session):
        self.session = session

    def create(self, producer: Producer) -> Producer:
        """Create a new producer."""
        db_item = ProducerDB(
            id=str(producer.id),
            canonical_name=producer.canonical_name,
            aliases_json=json.dumps(producer.aliases),
            country=producer.country,
            region=producer.region,
            website=producer.website,
            wikidata_id=producer.wikidata_id,
            created_at=producer.created_at,
            updated_at=producer.updated_at,
        )
        self.session.add(db_item)
        self.session.flush()
        return self._to_domain(db_item)

    def get_by_id(self, producer_id: UUID | str) -> Producer | None:
        """Get a producer by ID."""
        stmt = select(ProducerDB).where(ProducerDB.id == str(producer_id))
        db_item = self.session.execute(stmt).scalar_one_or_none()
        return self._to_domain(db_item) if db_item else None

    def get_by_wikidata_id(self, wikidata_id: str) -> Producer | None:
        """Get a producer by Wikidata ID."""
        stmt = select(ProducerDB).where(ProducerDB.wikidata_id == wikidata_id)
        db_item = self.session.execute(stmt).scalar_one_or_none()
        return self._to_domain(db_item) if db_item else None

    def search_by_name(self, name: str, limit: int = 20) -> list[Producer]:
        """Search producers by name (partial match)."""
        stmt = (
            select(ProducerDB)
            .where(ProducerDB.canonical_name.ilike(f"%{name}%"))
            .order_by(ProducerDB.canonical_name)
            .limit(limit)
        )
        result = self.session.execute(stmt).scalars().all()
        return [self._to_domain(p) for p in result]

    def list_all(self, limit: int = 100, offset: int = 0) -> list[Producer]:
        """List all producers with pagination."""
        stmt = (
            select(ProducerDB)
            .order_by(ProducerDB.canonical_name)
            .limit(limit)
            .offset(offset)
        )
        result = self.session.execute(stmt).scalars().all()
        return [self._to_domain(p) for p in result]

    def count(self) -> int:
        """Get total count of producers."""
        stmt = select(func.count()).select_from(ProducerDB)
        return self.session.execute(stmt).scalar() or 0

    def update(self, producer: Producer) -> Producer:
        """Update an existing producer."""
        stmt = select(ProducerDB).where(ProducerDB.id == str(producer.id))
        db_item = self.session.execute(stmt).scalar_one_or_none()
        if db_item is None:
            raise ValueError(f"Producer with id {producer.id} not found")

        db_item.canonical_name = producer.canonical_name
        db_item.aliases_json = json.dumps(producer.aliases)
        db_item.country = producer.country
        db_item.region = producer.region
        db_item.website = producer.website
        db_item.wikidata_id = producer.wikidata_id
        db_item.updated_at = _utc_now()

        self.session.flush()
        return self._to_domain(db_item)

    def delete(self, producer_id: UUID | str) -> bool:
        """Delete a producer by ID."""
        stmt = select(ProducerDB).where(ProducerDB.id == str(producer_id))
        db_item = self.session.execute(stmt).scalar_one_or_none()
        if db_item is None:
            return False
        self.session.delete(db_item)
        self.session.flush()
        return True

    def _to_domain(self, db_item: ProducerDB) -> Producer:
        """Convert DB model to domain model."""
        return Producer(
            id=UUID(db_item.id),
            canonical_name=db_item.canonical_name,
            aliases=json.loads(db_item.aliases_json),
            country=db_item.country,
            region=db_item.region,
            website=db_item.website,
            wikidata_id=db_item.wikidata_id,
            created_at=db_item.created_at,
            updated_at=db_item.updated_at,
        )


class WineRepository:
    """Repository for Wine CRUD operations."""

    def __init__(self, session: Session):
        self.session = session

    def create(self, wine: Wine) -> Wine:
        """Create a new wine."""
        db_item = WineDB(
            id=str(wine.id),
            producer_id=str(wine.producer_id),
            canonical_name=wine.canonical_name,
            aliases_json=json.dumps(wine.aliases),
            color=wine.color.value if wine.color else None,
            style=wine.style.value if wine.style else None,
            grapes_json=json.dumps(wine.grapes),
            appellation=wine.appellation,
            region_id=str(wine.region_id) if wine.region_id else None,
            created_at=wine.created_at,
            updated_at=wine.updated_at,
        )
        self.session.add(db_item)
        self.session.flush()
        return self._to_domain(db_item)

    def get_by_id(self, wine_id: UUID | str) -> Wine | None:
        """Get a wine by ID."""
        stmt = select(WineDB).where(WineDB.id == str(wine_id))
        db_item = self.session.execute(stmt).scalar_one_or_none()
        return self._to_domain(db_item) if db_item else None

    def get_by_producer_id(self, producer_id: UUID | str) -> list[Wine]:
        """Get all wines for a producer."""
        stmt = (
            select(WineDB)
            .where(WineDB.producer_id == str(producer_id))
            .order_by(WineDB.canonical_name)
        )
        result = self.session.execute(stmt).scalars().all()
        return [self._to_domain(w) for w in result]

    def search_by_name(self, name: str, limit: int = 20) -> list[Wine]:
        """Search wines by name (partial match)."""
        stmt = (
            select(WineDB)
            .where(WineDB.canonical_name.ilike(f"%{name}%"))
            .order_by(WineDB.canonical_name)
            .limit(limit)
        )
        result = self.session.execute(stmt).scalars().all()
        return [self._to_domain(w) for w in result]

    def count(self) -> int:
        """Get total count of wines."""
        stmt = select(func.count()).select_from(WineDB)
        return self.session.execute(stmt).scalar() or 0

    def update(self, wine: Wine) -> Wine:
        """Update an existing wine."""
        stmt = select(WineDB).where(WineDB.id == str(wine.id))
        db_item = self.session.execute(stmt).scalar_one_or_none()
        if db_item is None:
            raise ValueError(f"Wine with id {wine.id} not found")

        db_item.producer_id = str(wine.producer_id)
        db_item.canonical_name = wine.canonical_name
        db_item.aliases_json = json.dumps(wine.aliases)
        db_item.color = wine.color.value if wine.color else None
        db_item.style = wine.style.value if wine.style else None
        db_item.grapes_json = json.dumps(wine.grapes)
        db_item.appellation = wine.appellation
        db_item.region_id = str(wine.region_id) if wine.region_id else None
        db_item.updated_at = _utc_now()

        self.session.flush()
        return self._to_domain(db_item)

    def delete(self, wine_id: UUID | str) -> bool:
        """Delete a wine by ID."""
        stmt = select(WineDB).where(WineDB.id == str(wine_id))
        db_item = self.session.execute(stmt).scalar_one_or_none()
        if db_item is None:
            return False
        self.session.delete(db_item)
        self.session.flush()
        return True

    def _to_domain(self, db_item: WineDB) -> Wine:
        """Convert DB model to domain model."""
        from wine_agent.core.enums import WineColor, WineStyle

        return Wine(
            id=UUID(db_item.id),
            producer_id=UUID(db_item.producer_id),
            canonical_name=db_item.canonical_name,
            aliases=json.loads(db_item.aliases_json),
            color=WineColor(db_item.color) if db_item.color else None,
            style=WineStyle(db_item.style) if db_item.style else None,
            grapes=json.loads(db_item.grapes_json),
            appellation=db_item.appellation,
            region_id=UUID(db_item.region_id) if db_item.region_id else None,
            created_at=db_item.created_at,
            updated_at=db_item.updated_at,
        )


class VintageRepository:
    """Repository for Vintage CRUD operations."""

    def __init__(self, session: Session):
        self.session = session

    def create(self, vintage: Vintage) -> Vintage:
        """Create a new vintage."""
        db_item = VintageDB(
            id=str(vintage.id),
            wine_id=str(vintage.wine_id),
            year=vintage.year,
            bottle_size_ml=vintage.bottle_size_ml,
            abv=vintage.abv,
            tech_sheet_attrs_json=json.dumps(vintage.tech_sheet_attrs),
            created_at=vintage.created_at,
            updated_at=vintage.updated_at,
        )
        self.session.add(db_item)
        self.session.flush()
        return self._to_domain(db_item)

    def get_by_id(self, vintage_id: UUID | str) -> Vintage | None:
        """Get a vintage by ID."""
        stmt = select(VintageDB).where(VintageDB.id == str(vintage_id))
        db_item = self.session.execute(stmt).scalar_one_or_none()
        return self._to_domain(db_item) if db_item else None

    def get_by_wine_id(self, wine_id: UUID | str) -> list[Vintage]:
        """Get all vintages for a wine."""
        stmt = (
            select(VintageDB)
            .where(VintageDB.wine_id == str(wine_id))
            .order_by(VintageDB.year.desc())
        )
        result = self.session.execute(stmt).scalars().all()
        return [self._to_domain(v) for v in result]

    def get_by_wine_and_year(self, wine_id: UUID | str, year: int) -> Vintage | None:
        """Get a specific vintage by wine ID and year."""
        stmt = select(VintageDB).where(
            VintageDB.wine_id == str(wine_id),
            VintageDB.year == year,
        )
        db_item = self.session.execute(stmt).scalar_one_or_none()
        return self._to_domain(db_item) if db_item else None

    def count(self) -> int:
        """Get total count of vintages."""
        stmt = select(func.count()).select_from(VintageDB)
        return self.session.execute(stmt).scalar() or 0

    def update(self, vintage: Vintage) -> Vintage:
        """Update an existing vintage."""
        stmt = select(VintageDB).where(VintageDB.id == str(vintage.id))
        db_item = self.session.execute(stmt).scalar_one_or_none()
        if db_item is None:
            raise ValueError(f"Vintage with id {vintage.id} not found")

        db_item.wine_id = str(vintage.wine_id)
        db_item.year = vintage.year
        db_item.bottle_size_ml = vintage.bottle_size_ml
        db_item.abv = vintage.abv
        db_item.tech_sheet_attrs_json = json.dumps(vintage.tech_sheet_attrs)
        db_item.updated_at = _utc_now()

        self.session.flush()
        return self._to_domain(db_item)

    def delete(self, vintage_id: UUID | str) -> bool:
        """Delete a vintage by ID."""
        stmt = select(VintageDB).where(VintageDB.id == str(vintage_id))
        db_item = self.session.execute(stmt).scalar_one_or_none()
        if db_item is None:
            return False
        self.session.delete(db_item)
        self.session.flush()
        return True

    def _to_domain(self, db_item: VintageDB) -> Vintage:
        """Convert DB model to domain model."""
        return Vintage(
            id=UUID(db_item.id),
            wine_id=UUID(db_item.wine_id),
            year=db_item.year,
            bottle_size_ml=db_item.bottle_size_ml,
            abv=db_item.abv,
            tech_sheet_attrs=json.loads(db_item.tech_sheet_attrs_json),
            created_at=db_item.created_at,
            updated_at=db_item.updated_at,
        )


# ============================================================================
# Reference Entity Repositories
# ============================================================================


class RegionRepository:
    """Repository for Region CRUD operations."""

    def __init__(self, session: Session):
        self.session = session

    def create(self, region: Region) -> Region:
        """Create a new region."""
        db_item = RegionDB(
            id=str(region.id),
            parent_id=str(region.parent_id) if region.parent_id else None,
            name=region.name,
            aliases_json=json.dumps(region.aliases),
            country=region.country,
            wikidata_id=region.wikidata_id,
            hierarchy_level=region.hierarchy_level.value,
            created_at=region.created_at,
            updated_at=region.updated_at,
        )
        self.session.add(db_item)
        self.session.flush()
        return self._to_domain(db_item)

    def get_by_id(self, region_id: UUID | str) -> Region | None:
        """Get a region by ID."""
        stmt = select(RegionDB).where(RegionDB.id == str(region_id))
        db_item = self.session.execute(stmt).scalar_one_or_none()
        return self._to_domain(db_item) if db_item else None

    def get_by_wikidata_id(self, wikidata_id: str) -> Region | None:
        """Get a region by Wikidata ID."""
        stmt = select(RegionDB).where(RegionDB.wikidata_id == wikidata_id)
        db_item = self.session.execute(stmt).scalar_one_or_none()
        return self._to_domain(db_item) if db_item else None

    def search_by_name(self, name: str, limit: int = 20) -> list[Region]:
        """Search regions by name (partial match)."""
        stmt = (
            select(RegionDB)
            .where(RegionDB.name.ilike(f"%{name}%"))
            .order_by(RegionDB.name)
            .limit(limit)
        )
        result = self.session.execute(stmt).scalars().all()
        return [self._to_domain(r) for r in result]

    def get_by_country(self, country: str) -> list[Region]:
        """Get all regions for a country."""
        stmt = (
            select(RegionDB)
            .where(RegionDB.country == country)
            .order_by(RegionDB.name)
        )
        result = self.session.execute(stmt).scalars().all()
        return [self._to_domain(r) for r in result]

    def get_children(self, parent_id: UUID | str) -> list[Region]:
        """Get child regions of a parent region."""
        stmt = (
            select(RegionDB)
            .where(RegionDB.parent_id == str(parent_id))
            .order_by(RegionDB.name)
        )
        result = self.session.execute(stmt).scalars().all()
        return [self._to_domain(r) for r in result]

    def count(self) -> int:
        """Get total count of regions."""
        stmt = select(func.count()).select_from(RegionDB)
        return self.session.execute(stmt).scalar() or 0

    def _to_domain(self, db_item: RegionDB) -> Region:
        """Convert DB model to domain model."""
        from wine_agent.core.schema_canonical import RegionHierarchyLevel

        return Region(
            id=UUID(db_item.id),
            parent_id=UUID(db_item.parent_id) if db_item.parent_id else None,
            name=db_item.name,
            aliases=json.loads(db_item.aliases_json),
            country=db_item.country,
            wikidata_id=db_item.wikidata_id,
            hierarchy_level=RegionHierarchyLevel(db_item.hierarchy_level),
            created_at=db_item.created_at,
            updated_at=db_item.updated_at,
        )


class GrapeVarietyRepository:
    """Repository for GrapeVariety CRUD operations."""

    def __init__(self, session: Session):
        self.session = session

    def create(self, grape: GrapeVariety) -> GrapeVariety:
        """Create a new grape variety."""
        db_item = GrapeVarietyDB(
            id=str(grape.id),
            canonical_name=grape.canonical_name,
            aliases_json=json.dumps(grape.aliases),
            wikidata_id=grape.wikidata_id,
            created_at=grape.created_at,
            updated_at=grape.updated_at,
        )
        self.session.add(db_item)
        self.session.flush()
        return self._to_domain(db_item)

    def get_by_id(self, grape_id: UUID | str) -> GrapeVariety | None:
        """Get a grape variety by ID."""
        stmt = select(GrapeVarietyDB).where(GrapeVarietyDB.id == str(grape_id))
        db_item = self.session.execute(stmt).scalar_one_or_none()
        return self._to_domain(db_item) if db_item else None

    def get_by_wikidata_id(self, wikidata_id: str) -> GrapeVariety | None:
        """Get a grape variety by Wikidata ID."""
        stmt = select(GrapeVarietyDB).where(GrapeVarietyDB.wikidata_id == wikidata_id)
        db_item = self.session.execute(stmt).scalar_one_or_none()
        return self._to_domain(db_item) if db_item else None

    def search_by_name(self, name: str, limit: int = 20) -> list[GrapeVariety]:
        """Search grape varieties by name (partial match)."""
        stmt = (
            select(GrapeVarietyDB)
            .where(GrapeVarietyDB.canonical_name.ilike(f"%{name}%"))
            .order_by(GrapeVarietyDB.canonical_name)
            .limit(limit)
        )
        result = self.session.execute(stmt).scalars().all()
        return [self._to_domain(g) for g in result]

    def list_all(self, limit: int = 100, offset: int = 0) -> list[GrapeVariety]:
        """List all grape varieties with pagination."""
        stmt = (
            select(GrapeVarietyDB)
            .order_by(GrapeVarietyDB.canonical_name)
            .limit(limit)
            .offset(offset)
        )
        result = self.session.execute(stmt).scalars().all()
        return [self._to_domain(g) for g in result]

    def count(self) -> int:
        """Get total count of grape varieties."""
        stmt = select(func.count()).select_from(GrapeVarietyDB)
        return self.session.execute(stmt).scalar() or 0

    def _to_domain(self, db_item: GrapeVarietyDB) -> GrapeVariety:
        """Convert DB model to domain model."""
        return GrapeVariety(
            id=UUID(db_item.id),
            canonical_name=db_item.canonical_name,
            aliases=json.loads(db_item.aliases_json),
            wikidata_id=db_item.wikidata_id,
            created_at=db_item.created_at,
            updated_at=db_item.updated_at,
        )


# ============================================================================
# Trade Entity Repositories
# ============================================================================


class ImporterRepository:
    """Repository for Importer CRUD operations."""

    def __init__(self, session: Session):
        self.session = session

    def create(self, importer: Importer) -> Importer:
        """Create a new importer."""
        db_item = ImporterDB(
            id=str(importer.id),
            canonical_name=importer.canonical_name,
            country=importer.country,
            website=importer.website,
            created_at=importer.created_at,
            updated_at=importer.updated_at,
        )
        self.session.add(db_item)
        self.session.flush()
        return self._to_domain(db_item)

    def get_by_id(self, importer_id: UUID | str) -> Importer | None:
        """Get an importer by ID."""
        stmt = select(ImporterDB).where(ImporterDB.id == str(importer_id))
        db_item = self.session.execute(stmt).scalar_one_or_none()
        return self._to_domain(db_item) if db_item else None

    def search_by_name(self, name: str, limit: int = 20) -> list[Importer]:
        """Search importers by name (partial match)."""
        stmt = (
            select(ImporterDB)
            .where(ImporterDB.canonical_name.ilike(f"%{name}%"))
            .order_by(ImporterDB.canonical_name)
            .limit(limit)
        )
        result = self.session.execute(stmt).scalars().all()
        return [self._to_domain(i) for i in result]

    def count(self) -> int:
        """Get total count of importers."""
        stmt = select(func.count()).select_from(ImporterDB)
        return self.session.execute(stmt).scalar() or 0

    def _to_domain(self, db_item: ImporterDB) -> Importer:
        """Convert DB model to domain model."""
        return Importer(
            id=UUID(db_item.id),
            canonical_name=db_item.canonical_name,
            country=db_item.country,
            website=db_item.website,
            created_at=db_item.created_at,
            updated_at=db_item.updated_at,
        )


class DistributorRepository:
    """Repository for Distributor CRUD operations."""

    def __init__(self, session: Session):
        self.session = session

    def create(self, distributor: Distributor) -> Distributor:
        """Create a new distributor."""
        db_item = DistributorDB(
            id=str(distributor.id),
            canonical_name=distributor.canonical_name,
            country=distributor.country,
            website=distributor.website,
            regions_served_json=json.dumps(distributor.regions_served),
            created_at=distributor.created_at,
            updated_at=distributor.updated_at,
        )
        self.session.add(db_item)
        self.session.flush()
        return self._to_domain(db_item)

    def get_by_id(self, distributor_id: UUID | str) -> Distributor | None:
        """Get a distributor by ID."""
        stmt = select(DistributorDB).where(DistributorDB.id == str(distributor_id))
        db_item = self.session.execute(stmt).scalar_one_or_none()
        return self._to_domain(db_item) if db_item else None

    def search_by_name(self, name: str, limit: int = 20) -> list[Distributor]:
        """Search distributors by name (partial match)."""
        stmt = (
            select(DistributorDB)
            .where(DistributorDB.canonical_name.ilike(f"%{name}%"))
            .order_by(DistributorDB.canonical_name)
            .limit(limit)
        )
        result = self.session.execute(stmt).scalars().all()
        return [self._to_domain(d) for d in result]

    def count(self) -> int:
        """Get total count of distributors."""
        stmt = select(func.count()).select_from(DistributorDB)
        return self.session.execute(stmt).scalar() or 0

    def _to_domain(self, db_item: DistributorDB) -> Distributor:
        """Convert DB model to domain model."""
        return Distributor(
            id=UUID(db_item.id),
            canonical_name=db_item.canonical_name,
            country=db_item.country,
            website=db_item.website,
            regions_served=json.loads(db_item.regions_served_json),
            created_at=db_item.created_at,
            updated_at=db_item.updated_at,
        )


# ============================================================================
# Ingestion Entity Repositories
# ============================================================================


class SourceRepository:
    """Repository for Source CRUD operations."""

    def __init__(self, session: Session):
        self.session = session

    def create(self, source: Source) -> Source:
        """Create a new source."""
        db_item = SourceDB(
            id=str(source.id),
            domain=source.domain,
            adapter_type=source.adapter_type,
            rate_limit_config_json=json.dumps(source.rate_limit_config),
            allowlist_json=json.dumps(source.allowlist),
            denylist_json=json.dumps(source.denylist),
            enabled=source.enabled,
            created_at=source.created_at,
            updated_at=source.updated_at,
        )
        self.session.add(db_item)
        self.session.flush()
        return self._to_domain(db_item)

    def get_by_id(self, source_id: UUID | str) -> Source | None:
        """Get a source by ID."""
        stmt = select(SourceDB).where(SourceDB.id == str(source_id))
        db_item = self.session.execute(stmt).scalar_one_or_none()
        return self._to_domain(db_item) if db_item else None

    def get_by_domain(self, domain: str) -> Source | None:
        """Get a source by domain."""
        stmt = select(SourceDB).where(SourceDB.domain == domain.lower())
        db_item = self.session.execute(stmt).scalar_one_or_none()
        return self._to_domain(db_item) if db_item else None

    def list_enabled(self) -> list[Source]:
        """List all enabled sources."""
        stmt = (
            select(SourceDB)
            .where(SourceDB.enabled == True)  # noqa: E712
            .order_by(SourceDB.domain)
        )
        result = self.session.execute(stmt).scalars().all()
        return [self._to_domain(s) for s in result]

    def list_all(self) -> list[Source]:
        """List all sources."""
        stmt = select(SourceDB).order_by(SourceDB.domain)
        result = self.session.execute(stmt).scalars().all()
        return [self._to_domain(s) for s in result]

    def count(self) -> int:
        """Get total count of sources."""
        stmt = select(func.count()).select_from(SourceDB)
        return self.session.execute(stmt).scalar() or 0

    def update(self, source: Source) -> Source:
        """Update an existing source."""
        stmt = select(SourceDB).where(SourceDB.id == str(source.id))
        db_item = self.session.execute(stmt).scalar_one_or_none()
        if db_item is None:
            raise ValueError(f"Source with id {source.id} not found")

        db_item.domain = source.domain
        db_item.adapter_type = source.adapter_type
        db_item.rate_limit_config_json = json.dumps(source.rate_limit_config)
        db_item.allowlist_json = json.dumps(source.allowlist)
        db_item.denylist_json = json.dumps(source.denylist)
        db_item.enabled = source.enabled
        db_item.updated_at = _utc_now()

        self.session.flush()
        return self._to_domain(db_item)

    def _to_domain(self, db_item: SourceDB) -> Source:
        """Convert DB model to domain model."""
        return Source(
            id=UUID(db_item.id),
            domain=db_item.domain,
            adapter_type=db_item.adapter_type,
            rate_limit_config=json.loads(db_item.rate_limit_config_json),
            allowlist=json.loads(db_item.allowlist_json),
            denylist=json.loads(db_item.denylist_json),
            enabled=db_item.enabled,
            created_at=db_item.created_at,
            updated_at=db_item.updated_at,
        )


class SnapshotRepository:
    """Repository for Snapshot CRUD operations."""

    def __init__(self, session: Session):
        self.session = session

    def create(self, snapshot: Snapshot) -> Snapshot:
        """Create a new snapshot."""
        db_item = SnapshotDB(
            id=str(snapshot.id),
            source_id=str(snapshot.source_id),
            url=snapshot.url,
            content_hash=snapshot.content_hash,
            mime_type=snapshot.mime_type,
            file_path=snapshot.file_path,
            fetched_at=snapshot.fetched_at,
            status=snapshot.status.value,
        )
        self.session.add(db_item)
        self.session.flush()
        return self._to_domain(db_item)

    def get_by_id(self, snapshot_id: UUID | str) -> Snapshot | None:
        """Get a snapshot by ID."""
        stmt = select(SnapshotDB).where(SnapshotDB.id == str(snapshot_id))
        db_item = self.session.execute(stmt).scalar_one_or_none()
        return self._to_domain(db_item) if db_item else None

    def get_by_content_hash(self, content_hash: str) -> Snapshot | None:
        """Get a snapshot by content hash (for deduplication)."""
        stmt = select(SnapshotDB).where(SnapshotDB.content_hash == content_hash)
        db_item = self.session.execute(stmt).scalar_one_or_none()
        return self._to_domain(db_item) if db_item else None

    def get_by_source_id(self, source_id: UUID | str, limit: int = 100) -> list[Snapshot]:
        """Get snapshots for a source."""
        stmt = (
            select(SnapshotDB)
            .where(SnapshotDB.source_id == str(source_id))
            .order_by(SnapshotDB.fetched_at.desc())
            .limit(limit)
        )
        result = self.session.execute(stmt).scalars().all()
        return [self._to_domain(s) for s in result]

    def count(self) -> int:
        """Get total count of snapshots."""
        stmt = select(func.count()).select_from(SnapshotDB)
        return self.session.execute(stmt).scalar() or 0

    def update_status(self, snapshot_id: UUID | str, status: str) -> Snapshot | None:
        """Update snapshot status."""
        stmt = select(SnapshotDB).where(SnapshotDB.id == str(snapshot_id))
        db_item = self.session.execute(stmt).scalar_one_or_none()
        if db_item is None:
            return None
        db_item.status = status
        self.session.flush()
        return self._to_domain(db_item)

    def _to_domain(self, db_item: SnapshotDB) -> Snapshot:
        """Convert DB model to domain model."""
        from wine_agent.core.schema_canonical import SnapshotStatus

        return Snapshot(
            id=UUID(db_item.id),
            source_id=UUID(db_item.source_id),
            url=db_item.url,
            content_hash=db_item.content_hash,
            mime_type=db_item.mime_type,
            file_path=db_item.file_path,
            fetched_at=db_item.fetched_at,
            status=SnapshotStatus(db_item.status),
        )


class ListingRepository:
    """Repository for Listing CRUD operations."""

    def __init__(self, session: Session):
        self.session = session

    def create(self, listing: Listing) -> Listing:
        """Create a new listing."""
        db_item = ListingDB(
            id=str(listing.id),
            source_id=str(listing.source_id),
            snapshot_id=str(listing.snapshot_id),
            url=listing.url,
            title=listing.title,
            sku=listing.sku,
            upc=listing.upc,
            ean=listing.ean,
            price=listing.price,
            currency=listing.currency,
            parsed_fields_json=json.dumps(listing.parsed_fields),
            created_at=listing.created_at,
        )
        self.session.add(db_item)
        self.session.flush()
        return self._to_domain(db_item)

    def get_by_id(self, listing_id: UUID | str) -> Listing | None:
        """Get a listing by ID."""
        stmt = select(ListingDB).where(ListingDB.id == str(listing_id))
        db_item = self.session.execute(stmt).scalar_one_or_none()
        return self._to_domain(db_item) if db_item else None

    def get_by_upc(self, upc: str) -> list[Listing]:
        """Get listings by UPC code."""
        stmt = select(ListingDB).where(ListingDB.upc == upc)
        result = self.session.execute(stmt).scalars().all()
        return [self._to_domain(l) for l in result]

    def get_by_ean(self, ean: str) -> list[Listing]:
        """Get listings by EAN code."""
        stmt = select(ListingDB).where(ListingDB.ean == ean)
        result = self.session.execute(stmt).scalars().all()
        return [self._to_domain(l) for l in result]

    def get_by_source_id(self, source_id: UUID | str, limit: int = 100) -> list[Listing]:
        """Get listings for a source."""
        stmt = (
            select(ListingDB)
            .where(ListingDB.source_id == str(source_id))
            .order_by(ListingDB.created_at.desc())
            .limit(limit)
        )
        result = self.session.execute(stmt).scalars().all()
        return [self._to_domain(l) for l in result]

    def count(self) -> int:
        """Get total count of listings."""
        stmt = select(func.count()).select_from(ListingDB)
        return self.session.execute(stmt).scalar() or 0

    def _to_domain(self, db_item: ListingDB) -> Listing:
        """Convert DB model to domain model."""
        return Listing(
            id=UUID(db_item.id),
            source_id=UUID(db_item.source_id),
            snapshot_id=UUID(db_item.snapshot_id),
            url=db_item.url,
            title=db_item.title,
            sku=db_item.sku,
            upc=db_item.upc,
            ean=db_item.ean,
            price=db_item.price,
            currency=db_item.currency,
            parsed_fields=json.loads(db_item.parsed_fields_json),
            created_at=db_item.created_at,
        )


class ListingMatchRepository:
    """Repository for ListingMatch CRUD operations."""

    def __init__(self, session: Session):
        self.session = session

    def create(self, match: ListingMatch) -> ListingMatch:
        """Create a new listing match."""
        db_item = ListingMatchDB(
            id=str(match.id),
            listing_id=str(match.listing_id),
            entity_type=match.entity_type.value,
            entity_id=str(match.entity_id),
            confidence=match.confidence,
            decision=match.decision.value,
            created_at=match.created_at,
        )
        self.session.add(db_item)
        self.session.flush()
        return self._to_domain(db_item)

    def get_by_id(self, match_id: UUID | str) -> ListingMatch | None:
        """Get a listing match by ID."""
        stmt = select(ListingMatchDB).where(ListingMatchDB.id == str(match_id))
        db_item = self.session.execute(stmt).scalar_one_or_none()
        return self._to_domain(db_item) if db_item else None

    def get_by_listing_id(self, listing_id: UUID | str) -> list[ListingMatch]:
        """Get all matches for a listing."""
        stmt = (
            select(ListingMatchDB)
            .where(ListingMatchDB.listing_id == str(listing_id))
            .order_by(ListingMatchDB.confidence.desc())
        )
        result = self.session.execute(stmt).scalars().all()
        return [self._to_domain(m) for m in result]

    def get_by_entity(self, entity_type: str, entity_id: UUID | str) -> list[ListingMatch]:
        """Get all matches for an entity."""
        stmt = (
            select(ListingMatchDB)
            .where(
                ListingMatchDB.entity_type == entity_type,
                ListingMatchDB.entity_id == str(entity_id),
            )
            .order_by(ListingMatchDB.confidence.desc())
        )
        result = self.session.execute(stmt).scalars().all()
        return [self._to_domain(m) for m in result]

    def get_pending_review(self, min_confidence: float = 0.7, max_confidence: float = 0.9) -> list[ListingMatch]:
        """Get matches pending manual review (auto matches in confidence range)."""
        stmt = (
            select(ListingMatchDB)
            .where(
                ListingMatchDB.decision == "auto",
                ListingMatchDB.confidence >= min_confidence,
                ListingMatchDB.confidence < max_confidence,
            )
            .order_by(ListingMatchDB.confidence.desc())
        )
        result = self.session.execute(stmt).scalars().all()
        return [self._to_domain(m) for m in result]

    def update_decision(self, match_id: UUID | str, decision: str) -> ListingMatch | None:
        """Update match decision."""
        stmt = select(ListingMatchDB).where(ListingMatchDB.id == str(match_id))
        db_item = self.session.execute(stmt).scalar_one_or_none()
        if db_item is None:
            return None
        db_item.decision = decision
        self.session.flush()
        return self._to_domain(db_item)

    def _to_domain(self, db_item: ListingMatchDB) -> ListingMatch:
        """Convert DB model to domain model."""
        from wine_agent.core.schema_canonical import EntityType, MatchDecision

        return ListingMatch(
            id=UUID(db_item.id),
            listing_id=UUID(db_item.listing_id),
            entity_type=EntityType(db_item.entity_type),
            entity_id=UUID(db_item.entity_id),
            confidence=db_item.confidence,
            decision=MatchDecision(db_item.decision),
            created_at=db_item.created_at,
        )


# ============================================================================
# Provenance Repository
# ============================================================================


class FieldProvenanceRepository:
    """Repository for FieldProvenance CRUD operations."""

    def __init__(self, session: Session):
        self.session = session

    def create(self, provenance: FieldProvenance) -> FieldProvenance:
        """Create a new field provenance record."""
        db_item = FieldProvenanceDB(
            id=str(provenance.id),
            entity_type=provenance.entity_type.value,
            entity_id=str(provenance.entity_id),
            field_path=provenance.field_path,
            value_json=json.dumps(provenance.value),
            source_id=str(provenance.source_id),
            source_url=provenance.source_url,
            fetched_at=provenance.fetched_at,
            extractor_version=provenance.extractor_version,
            confidence=provenance.confidence,
            snapshot_id=str(provenance.snapshot_id) if provenance.snapshot_id else None,
            created_at=provenance.created_at,
        )
        self.session.add(db_item)
        self.session.flush()
        return self._to_domain(db_item)

    def get_by_entity(self, entity_type: str, entity_id: UUID | str) -> list[FieldProvenance]:
        """Get all provenance records for an entity."""
        stmt = (
            select(FieldProvenanceDB)
            .where(
                FieldProvenanceDB.entity_type == entity_type,
                FieldProvenanceDB.entity_id == str(entity_id),
            )
            .order_by(FieldProvenanceDB.field_path, FieldProvenanceDB.confidence.desc())
        )
        result = self.session.execute(stmt).scalars().all()
        return [self._to_domain(p) for p in result]

    def get_by_field(self, entity_type: str, entity_id: UUID | str, field_path: str) -> list[FieldProvenance]:
        """Get provenance records for a specific field."""
        stmt = (
            select(FieldProvenanceDB)
            .where(
                FieldProvenanceDB.entity_type == entity_type,
                FieldProvenanceDB.entity_id == str(entity_id),
                FieldProvenanceDB.field_path == field_path,
            )
            .order_by(FieldProvenanceDB.confidence.desc())
        )
        result = self.session.execute(stmt).scalars().all()
        return [self._to_domain(p) for p in result]

    def _to_domain(self, db_item: FieldProvenanceDB) -> FieldProvenance:
        """Convert DB model to domain model."""
        from wine_agent.core.schema_canonical import EntityType

        return FieldProvenance(
            id=UUID(db_item.id),
            entity_type=EntityType(db_item.entity_type),
            entity_id=UUID(db_item.entity_id),
            field_path=db_item.field_path,
            value=json.loads(db_item.value_json),
            source_id=UUID(db_item.source_id),
            source_url=db_item.source_url,
            fetched_at=db_item.fetched_at,
            extractor_version=db_item.extractor_version,
            confidence=db_item.confidence,
            snapshot_id=UUID(db_item.snapshot_id) if db_item.snapshot_id else None,
            created_at=db_item.created_at,
        )
