"""Catalog service for managing canonical wine entities.

This service provides business logic for:
- Creating and managing producers, wines, and vintages
- Searching the wine catalog
- Linking tasting notes to canonical wines
- Managing provenance data
"""

import logging
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from wine_agent.core.schema_canonical import (
    CatalogSearchRequest,
    CatalogSearchResult,
    CatalogStats,
    GrapeVariety,
    Producer,
    Region,
    Vintage,
    Wine,
)
from wine_agent.db.engine import get_session
from wine_agent.db.repositories_canonical import (
    GrapeVarietyRepository,
    ProducerRepository,
    RegionRepository,
    VintageRepository,
    WineRepository,
)
from wine_agent.services.meilisearch_service import MeilisearchService, get_meilisearch_service

logger = logging.getLogger(__name__)


class CatalogService:
    """Service for managing the canonical wine catalog."""

    def __init__(
        self,
        session: Session | None = None,
        meilisearch: MeilisearchService | None = None,
    ):
        """
        Initialize the catalog service.

        Args:
            session: SQLAlchemy session (optional, will create one if not provided)
            meilisearch: Meilisearch service instance (optional)
        """
        self._session = session
        self._meilisearch = meilisearch

    @property
    def session(self) -> Session:
        """Get or create a database session."""
        if self._session is None:
            self._session = get_session()
        return self._session

    @property
    def meilisearch(self) -> MeilisearchService:
        """Get or create the Meilisearch service."""
        if self._meilisearch is None:
            self._meilisearch = get_meilisearch_service()
        return self._meilisearch

    # =========================================================================
    # Producer Operations
    # =========================================================================

    def create_producer(
        self,
        canonical_name: str,
        country: str = "",
        region: str = "",
        aliases: list[str] | None = None,
        website: str = "",
        wikidata_id: str | None = None,
    ) -> Producer:
        """
        Create a new canonical producer.

        Args:
            canonical_name: The official/canonical name of the producer
            country: Country of origin
            region: Primary region
            aliases: Alternative names for the producer
            website: Producer's website URL
            wikidata_id: Wikidata identifier for linking

        Returns:
            The created Producer
        """
        producer = Producer(
            canonical_name=canonical_name,
            country=country,
            region=region,
            aliases=aliases or [],
            website=website,
            wikidata_id=wikidata_id,
        )

        repo = ProducerRepository(self.session)
        created = repo.create(producer)
        self.session.commit()

        # Index in Meilisearch
        self.meilisearch.index_producer(created)

        logger.info(f"Created producer: {created.canonical_name} ({created.id})")
        return created

    def get_producer(self, producer_id: UUID | str) -> Producer | None:
        """Get a producer by ID."""
        repo = ProducerRepository(self.session)
        return repo.get_by_id(producer_id)

    def search_producers(self, query: str, limit: int = 20) -> list[Producer]:
        """Search producers by name."""
        repo = ProducerRepository(self.session)
        return repo.search_by_name(query, limit)

    def update_producer(self, producer: Producer) -> Producer:
        """Update a producer."""
        repo = ProducerRepository(self.session)
        updated = repo.update(producer)
        self.session.commit()

        # Re-index in Meilisearch
        self.meilisearch.index_producer(updated)

        return updated

    # =========================================================================
    # Wine Operations
    # =========================================================================

    def create_wine(
        self,
        producer_id: UUID | str,
        canonical_name: str,
        color: str | None = None,
        style: str | None = None,
        grapes: list[str] | None = None,
        appellation: str = "",
        aliases: list[str] | None = None,
        region_id: UUID | str | None = None,
    ) -> Wine:
        """
        Create a new canonical wine.

        Args:
            producer_id: ID of the producer
            canonical_name: The official/canonical name of the wine
            color: Wine color (red, white, rose, etc.)
            style: Wine style (still, sparkling, fortified, etc.)
            grapes: List of grape varieties
            appellation: Wine appellation
            aliases: Alternative names for the wine
            region_id: ID of the wine region

        Returns:
            The created Wine
        """
        from wine_agent.core.enums import WineColor, WineStyle

        wine = Wine(
            producer_id=UUID(str(producer_id)),
            canonical_name=canonical_name,
            color=WineColor(color) if color else None,
            style=WineStyle(style) if style else None,
            grapes=grapes or [],
            appellation=appellation,
            aliases=aliases or [],
            region_id=UUID(str(region_id)) if region_id else None,
        )

        repo = WineRepository(self.session)
        created = repo.create(wine)
        self.session.commit()

        # Get producer for indexing
        producer = self.get_producer(producer_id)
        region = self.get_region(region_id) if region_id else None

        if producer:
            self.meilisearch.index_wine_without_vintage(created, producer, region)

        logger.info(f"Created wine: {created.canonical_name} ({created.id})")
        return created

    def get_wine(self, wine_id: UUID | str) -> Wine | None:
        """Get a wine by ID."""
        repo = WineRepository(self.session)
        return repo.get_by_id(wine_id)

    def get_wines_by_producer(self, producer_id: UUID | str) -> list[Wine]:
        """Get all wines for a producer."""
        repo = WineRepository(self.session)
        return repo.get_by_producer_id(producer_id)

    def search_wines(self, query: str, limit: int = 20) -> list[Wine]:
        """Search wines by name."""
        repo = WineRepository(self.session)
        return repo.search_by_name(query, limit)

    # =========================================================================
    # Vintage Operations
    # =========================================================================

    def create_vintage(
        self,
        wine_id: UUID | str,
        year: int,
        bottle_size_ml: int = 750,
        abv: float | None = None,
        tech_sheet_attrs: dict | None = None,
    ) -> Vintage:
        """
        Create a new canonical vintage.

        Args:
            wine_id: ID of the wine
            year: Vintage year
            bottle_size_ml: Bottle size in milliliters
            abv: Alcohol by volume percentage
            tech_sheet_attrs: Additional technical attributes

        Returns:
            The created Vintage
        """
        vintage = Vintage(
            wine_id=UUID(str(wine_id)),
            year=year,
            bottle_size_ml=bottle_size_ml,
            abv=abv,
            tech_sheet_attrs=tech_sheet_attrs or {},
        )

        repo = VintageRepository(self.session)
        created = repo.create(vintage)
        self.session.commit()

        # Get wine and producer for indexing
        wine = self.get_wine(wine_id)
        if wine:
            producer = self.get_producer(wine.producer_id)
            region = self.get_region(wine.region_id) if wine.region_id else None
            if producer:
                self.meilisearch.index_wine_vintage(created, wine, producer, region)

        logger.info(f"Created vintage: {wine_id} {year} ({created.id})")
        return created

    def get_vintage(self, vintage_id: UUID | str) -> Vintage | None:
        """Get a vintage by ID."""
        repo = VintageRepository(self.session)
        return repo.get_by_id(vintage_id)

    def get_vintages_by_wine(self, wine_id: UUID | str) -> list[Vintage]:
        """Get all vintages for a wine."""
        repo = VintageRepository(self.session)
        return repo.get_by_wine_id(wine_id)

    def get_or_create_vintage(
        self,
        wine_id: UUID | str,
        year: int,
        **kwargs: Any,
    ) -> tuple[Vintage, bool]:
        """
        Get an existing vintage or create a new one.

        Args:
            wine_id: ID of the wine
            year: Vintage year
            **kwargs: Additional vintage attributes

        Returns:
            Tuple of (Vintage, created_flag)
        """
        repo = VintageRepository(self.session)
        existing = repo.get_by_wine_and_year(wine_id, year)
        if existing:
            return existing, False

        created = self.create_vintage(wine_id, year, **kwargs)
        return created, True

    # =========================================================================
    # Region Operations
    # =========================================================================

    def create_region(
        self,
        name: str,
        country: str = "",
        parent_id: UUID | str | None = None,
        aliases: list[str] | None = None,
        hierarchy_level: str = "region",
        wikidata_id: str | None = None,
    ) -> Region:
        """Create a new region."""
        from wine_agent.core.schema_canonical import RegionHierarchyLevel

        region = Region(
            name=name,
            country=country,
            parent_id=UUID(str(parent_id)) if parent_id else None,
            aliases=aliases or [],
            hierarchy_level=RegionHierarchyLevel(hierarchy_level),
            wikidata_id=wikidata_id,
        )

        repo = RegionRepository(self.session)
        created = repo.create(region)
        self.session.commit()

        # Index in Meilisearch
        self.meilisearch.index_region(created)

        logger.info(f"Created region: {created.name} ({created.id})")
        return created

    def get_region(self, region_id: UUID | str) -> Region | None:
        """Get a region by ID."""
        repo = RegionRepository(self.session)
        return repo.get_by_id(region_id)

    def search_regions(self, query: str, limit: int = 20) -> list[Region]:
        """Search regions by name."""
        repo = RegionRepository(self.session)
        return repo.search_by_name(query, limit)

    # =========================================================================
    # Grape Variety Operations
    # =========================================================================

    def create_grape_variety(
        self,
        canonical_name: str,
        aliases: list[str] | None = None,
        wikidata_id: str | None = None,
    ) -> GrapeVariety:
        """Create a new grape variety."""
        grape = GrapeVariety(
            canonical_name=canonical_name,
            aliases=aliases or [],
            wikidata_id=wikidata_id,
        )

        repo = GrapeVarietyRepository(self.session)
        created = repo.create(grape)
        self.session.commit()

        logger.info(f"Created grape variety: {created.canonical_name} ({created.id})")
        return created

    def get_grape_variety(self, grape_id: UUID | str) -> GrapeVariety | None:
        """Get a grape variety by ID."""
        repo = GrapeVarietyRepository(self.session)
        return repo.get_by_id(grape_id)

    def search_grape_varieties(self, query: str, limit: int = 20) -> list[GrapeVariety]:
        """Search grape varieties by name."""
        repo = GrapeVarietyRepository(self.session)
        return repo.search_by_name(query, limit)

    # =========================================================================
    # Catalog Search
    # =========================================================================

    def search_catalog(
        self,
        request: CatalogSearchRequest,
    ) -> tuple[list[dict[str, Any]], int]:
        """
        Search the wine catalog using Meilisearch.

        Args:
            request: Search parameters

        Returns:
            Tuple of (results, total_count)
        """
        return self.meilisearch.search_wines(request)

    def search_catalog_full(
        self,
        request: CatalogSearchRequest,
    ) -> tuple[list[CatalogSearchResult], int]:
        """
        Search the wine catalog and return full entity objects.

        Args:
            request: Search parameters

        Returns:
            Tuple of (CatalogSearchResult list, total_count)
        """
        hits, total = self.meilisearch.search_wines(request)
        results = []

        for hit in hits:
            # Fetch full entities from database
            producer = self.get_producer(hit.get("producer_id")) if hit.get("producer_id") else None
            wine = self.get_wine(hit.get("wine_id")) if hit.get("wine_id") else None
            vintage = self.get_vintage(hit.get("vintage_id")) if hit.get("vintage_id") else None
            region = self.get_region(hit.get("region_id")) if hit.get("region_id") else None

            if wine and producer:
                results.append(CatalogSearchResult(
                    vintage=vintage,
                    wine=wine,
                    producer=producer,
                    region=region,
                    source_count=1,  # TODO: Count actual sources
                ))

        return results, total

    # =========================================================================
    # Tasting Note Linking
    # =========================================================================

    def link_tasting_to_vintage(
        self,
        tasting_note_id: UUID | str,
        vintage_id: UUID | str,
    ) -> bool:
        """
        Link a tasting note to a canonical vintage.

        Args:
            tasting_note_id: ID of the tasting note
            vintage_id: ID of the canonical vintage

        Returns:
            True if successful
        """
        from sqlalchemy import select, update

        from wine_agent.db.models import TastingNoteDB

        # Get the vintage to also link to wine
        vintage = self.get_vintage(vintage_id)
        if not vintage:
            logger.error(f"Vintage {vintage_id} not found")
            return False

        # Update tasting note with both vintage_id and wine_id
        stmt = (
            update(TastingNoteDB)
            .where(TastingNoteDB.id == str(tasting_note_id))
            .values(
                vintage_id=str(vintage_id),
                wine_id=str(vintage.wine_id),
            )
        )
        self.session.execute(stmt)
        self.session.commit()

        logger.info(f"Linked tasting note {tasting_note_id} to vintage {vintage_id}")
        return True

    def link_tasting_to_wine(
        self,
        tasting_note_id: UUID | str,
        wine_id: UUID | str,
    ) -> bool:
        """
        Link a tasting note to a canonical wine (when vintage is unknown).

        Args:
            tasting_note_id: ID of the tasting note
            wine_id: ID of the canonical wine

        Returns:
            True if successful
        """
        from sqlalchemy import update

        from wine_agent.db.models import TastingNoteDB

        stmt = (
            update(TastingNoteDB)
            .where(TastingNoteDB.id == str(tasting_note_id))
            .values(wine_id=str(wine_id))
        )
        self.session.execute(stmt)
        self.session.commit()

        logger.info(f"Linked tasting note {tasting_note_id} to wine {wine_id}")
        return True

    # =========================================================================
    # Statistics
    # =========================================================================

    def get_catalog_stats(self) -> CatalogStats:
        """Get statistics about the catalog."""
        producer_repo = ProducerRepository(self.session)
        wine_repo = WineRepository(self.session)
        vintage_repo = VintageRepository(self.session)
        region_repo = RegionRepository(self.session)
        grape_repo = GrapeVarietyRepository(self.session)

        from wine_agent.db.repositories_canonical import ListingRepository, SourceRepository

        source_repo = SourceRepository(self.session)
        listing_repo = ListingRepository(self.session)

        return CatalogStats(
            total_producers=producer_repo.count(),
            total_wines=wine_repo.count(),
            total_vintages=vintage_repo.count(),
            total_regions=region_repo.count(),
            total_grapes=grape_repo.count(),
            total_sources=source_repo.count(),
            total_listings=listing_repo.count(),
        )

    # =========================================================================
    # Index Management
    # =========================================================================

    def rebuild_search_index(self) -> None:
        """Rebuild the Meilisearch index from database."""
        logger.info("Rebuilding search index...")

        # Clear existing indexes
        self.meilisearch.clear_all_indexes()
        self.meilisearch.setup_indexes()

        # Re-index all producers
        producer_repo = ProducerRepository(self.session)
        producers = producer_repo.list_all(limit=10000)
        for producer in producers:
            self.meilisearch.index_producer(producer)

        # Re-index all regions
        region_repo = RegionRepository(self.session)
        regions = region_repo.search_by_name("", limit=10000)
        for region in regions:
            self.meilisearch.index_region(region)

        # Re-index all wines with vintages
        wine_repo = WineRepository(self.session)
        vintage_repo = VintageRepository(self.session)

        wines = wine_repo.search_by_name("", limit=10000)
        for wine in wines:
            producer = producer_repo.get_by_id(wine.producer_id)
            region = region_repo.get_by_id(wine.region_id) if wine.region_id else None

            vintages = vintage_repo.get_by_wine_id(wine.id)
            if vintages:
                for vintage in vintages:
                    if producer:
                        self.meilisearch.index_wine_vintage(vintage, wine, producer, region)
            elif producer:
                self.meilisearch.index_wine_without_vintage(wine, producer, region)

        logger.info("Search index rebuild complete")


# Convenience function for getting a service instance
def get_catalog_service(session: Session | None = None) -> CatalogService:
    """Get a catalog service instance."""
    return CatalogService(session=session)
