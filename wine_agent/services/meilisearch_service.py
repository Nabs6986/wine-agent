"""Meilisearch service for wine catalog search indexing.

This service manages the Meilisearch index for canonical wine entities,
providing fuzzy search, faceted filtering, and typo tolerance.
"""

import logging
import os
from typing import Any
from uuid import UUID

try:
    from meilisearch import Client
    from meilisearch.errors import MeilisearchApiError

    MEILISEARCH_AVAILABLE = True
except ImportError:
    MEILISEARCH_AVAILABLE = False
    Client = None
    MeilisearchApiError = Exception

from wine_agent.core.schema_canonical import (
    CatalogSearchRequest,
    CatalogSearchResult,
    Producer,
    Region,
    Vintage,
    Wine,
)

logger = logging.getLogger(__name__)

# Index names
WINES_INDEX = "wines"
PRODUCERS_INDEX = "producers"
REGIONS_INDEX = "regions"


class MeilisearchService:
    """Service for managing Meilisearch indexes for the wine catalog."""

    def __init__(
        self,
        url: str | None = None,
        api_key: str | None = None,
    ):
        """
        Initialize the Meilisearch service.

        Args:
            url: Meilisearch server URL (default: MEILISEARCH_URL env or localhost:7700)
            api_key: Meilisearch API key (default: MEILISEARCH_API_KEY env or None)
        """
        if not MEILISEARCH_AVAILABLE:
            logger.warning("Meilisearch package not installed. Search features will be unavailable.")
            self.client = None
            return

        self.url = url or os.getenv("MEILISEARCH_URL", "http://localhost:7700")
        self.api_key = api_key or os.getenv("MEILISEARCH_API_KEY")

        try:
            self.client = Client(self.url, self.api_key)
            # Test connection
            self.client.health()
            logger.info(f"Connected to Meilisearch at {self.url}")
        except Exception as e:
            logger.warning(f"Failed to connect to Meilisearch: {e}")
            self.client = None

    def is_available(self) -> bool:
        """Check if Meilisearch is available."""
        if not self.client:
            return False
        try:
            self.client.health()
            return True
        except Exception:
            return False

    def setup_indexes(self) -> None:
        """Set up Meilisearch indexes with proper configuration."""
        if not self.client:
            logger.warning("Meilisearch not available, skipping index setup")
            return

        # Create wines index with searchable/filterable attributes
        try:
            wines_index = self.client.index(WINES_INDEX)

            # Update settings for optimal wine search
            wines_index.update_settings({
                "searchableAttributes": [
                    "producer_name",
                    "wine_name",
                    "producer_aliases",
                    "wine_aliases",
                    "appellation",
                    "region_name",
                    "country",
                    "grapes",
                ],
                "filterableAttributes": [
                    "producer_id",
                    "wine_id",
                    "vintage_id",
                    "year",
                    "color",
                    "style",
                    "country",
                    "region_name",
                    "appellation",
                    "grapes",
                ],
                "sortableAttributes": [
                    "year",
                    "producer_name",
                    "wine_name",
                ],
                "rankingRules": [
                    "words",
                    "typo",
                    "proximity",
                    "attribute",
                    "sort",
                    "exactness",
                ],
                # Enable typo tolerance
                "typoTolerance": {
                    "enabled": True,
                    "minWordSizeForTypos": {
                        "oneTypo": 4,
                        "twoTypos": 8,
                    },
                },
            })
            logger.info("Wines index configured successfully")
        except MeilisearchApiError as e:
            logger.error(f"Failed to configure wines index: {e}")

        # Create producers index
        try:
            producers_index = self.client.index(PRODUCERS_INDEX)
            producers_index.update_settings({
                "searchableAttributes": [
                    "canonical_name",
                    "aliases",
                    "country",
                    "region",
                ],
                "filterableAttributes": [
                    "country",
                    "region",
                    "wikidata_id",
                ],
                "sortableAttributes": [
                    "canonical_name",
                ],
            })
            logger.info("Producers index configured successfully")
        except MeilisearchApiError as e:
            logger.error(f"Failed to configure producers index: {e}")

        # Create regions index
        try:
            regions_index = self.client.index(REGIONS_INDEX)
            regions_index.update_settings({
                "searchableAttributes": [
                    "name",
                    "aliases",
                    "country",
                ],
                "filterableAttributes": [
                    "country",
                    "hierarchy_level",
                    "parent_id",
                ],
                "sortableAttributes": [
                    "name",
                ],
            })
            logger.info("Regions index configured successfully")
        except MeilisearchApiError as e:
            logger.error(f"Failed to configure regions index: {e}")

    # =========================================================================
    # Indexing Methods
    # =========================================================================

    def index_wine_vintage(
        self,
        vintage: Vintage,
        wine: Wine,
        producer: Producer,
        region: Region | None = None,
    ) -> None:
        """
        Index a wine vintage for search.

        Creates a composite document combining vintage, wine, producer, and region
        information for comprehensive search.
        """
        if not self.client:
            return

        document = {
            "id": str(vintage.id),
            "vintage_id": str(vintage.id),
            "wine_id": str(wine.id),
            "producer_id": str(producer.id),
            "year": vintage.year,
            "bottle_size_ml": vintage.bottle_size_ml,
            "abv": vintage.abv,
            # Wine info
            "wine_name": wine.canonical_name,
            "wine_aliases": wine.aliases,
            "color": wine.color.value if wine.color else None,
            "style": wine.style.value if wine.style else None,
            "grapes": wine.grapes,
            "appellation": wine.appellation,
            # Producer info
            "producer_name": producer.canonical_name,
            "producer_aliases": producer.aliases,
            "country": producer.country,
            # Region info (if available)
            "region_name": region.name if region else "",
            "region_id": str(region.id) if region else None,
        }

        try:
            self.client.index(WINES_INDEX).add_documents([document])
            logger.debug(f"Indexed vintage {vintage.id}")
        except MeilisearchApiError as e:
            logger.error(f"Failed to index vintage {vintage.id}: {e}")

    def index_wine_without_vintage(
        self,
        wine: Wine,
        producer: Producer,
        region: Region | None = None,
    ) -> None:
        """
        Index a wine without a specific vintage.

        Useful for wines where vintage is unknown or non-vintage (NV).
        """
        if not self.client:
            return

        document = {
            "id": f"wine_{wine.id}",
            "vintage_id": None,
            "wine_id": str(wine.id),
            "producer_id": str(producer.id),
            "year": None,
            "bottle_size_ml": 750,
            "abv": None,
            "wine_name": wine.canonical_name,
            "wine_aliases": wine.aliases,
            "color": wine.color.value if wine.color else None,
            "style": wine.style.value if wine.style else None,
            "grapes": wine.grapes,
            "appellation": wine.appellation,
            "producer_name": producer.canonical_name,
            "producer_aliases": producer.aliases,
            "country": producer.country,
            "region_name": region.name if region else "",
            "region_id": str(region.id) if region else None,
        }

        try:
            self.client.index(WINES_INDEX).add_documents([document])
            logger.debug(f"Indexed wine {wine.id}")
        except MeilisearchApiError as e:
            logger.error(f"Failed to index wine {wine.id}: {e}")

    def index_producer(self, producer: Producer) -> None:
        """Index a producer for search."""
        if not self.client:
            return

        document = {
            "id": str(producer.id),
            "canonical_name": producer.canonical_name,
            "aliases": producer.aliases,
            "country": producer.country,
            "region": producer.region,
            "website": producer.website,
            "wikidata_id": producer.wikidata_id,
        }

        try:
            self.client.index(PRODUCERS_INDEX).add_documents([document])
            logger.debug(f"Indexed producer {producer.id}")
        except MeilisearchApiError as e:
            logger.error(f"Failed to index producer {producer.id}: {e}")

    def index_region(self, region: Region) -> None:
        """Index a region for search."""
        if not self.client:
            return

        document = {
            "id": str(region.id),
            "name": region.name,
            "aliases": region.aliases,
            "country": region.country,
            "hierarchy_level": region.hierarchy_level.value,
            "parent_id": str(region.parent_id) if region.parent_id else None,
            "wikidata_id": region.wikidata_id,
        }

        try:
            self.client.index(REGIONS_INDEX).add_documents([document])
            logger.debug(f"Indexed region {region.id}")
        except MeilisearchApiError as e:
            logger.error(f"Failed to index region {region.id}: {e}")

    def bulk_index_wines(self, documents: list[dict]) -> None:
        """Bulk index wine documents."""
        if not self.client or not documents:
            return

        try:
            self.client.index(WINES_INDEX).add_documents(documents)
            logger.info(f"Bulk indexed {len(documents)} wine documents")
        except MeilisearchApiError as e:
            logger.error(f"Failed to bulk index wines: {e}")

    def bulk_index_producers(self, documents: list[dict]) -> None:
        """Bulk index producer documents."""
        if not self.client or not documents:
            return

        try:
            self.client.index(PRODUCERS_INDEX).add_documents(documents)
            logger.info(f"Bulk indexed {len(documents)} producer documents")
        except MeilisearchApiError as e:
            logger.error(f"Failed to bulk index producers: {e}")

    # =========================================================================
    # Search Methods
    # =========================================================================

    def search_wines(
        self,
        request: CatalogSearchRequest,
    ) -> tuple[list[dict[str, Any]], int]:
        """
        Search the wine catalog.

        Args:
            request: Search parameters including query, filters, and pagination.

        Returns:
            Tuple of (results list, total hits count)
        """
        if not self.client:
            return [], 0

        # Build filter conditions
        filters = []
        if request.country:
            filters.append(f'country = "{request.country}"')
        if request.vintage_year:
            filters.append(f"year = {request.vintage_year}")
        if request.region:
            filters.append(f'region_name = "{request.region}"')
        if request.grape:
            filters.append(f'grapes = "{request.grape}"')

        filter_str = " AND ".join(filters) if filters else None

        # Calculate offset for pagination
        offset = (request.page - 1) * request.page_size

        try:
            result = self.client.index(WINES_INDEX).search(
                request.query or "",
                {
                    "filter": filter_str,
                    "limit": request.page_size,
                    "offset": offset,
                    "attributesToRetrieve": [
                        "id",
                        "vintage_id",
                        "wine_id",
                        "producer_id",
                        "year",
                        "wine_name",
                        "producer_name",
                        "country",
                        "region_name",
                        "appellation",
                        "grapes",
                        "color",
                        "style",
                    ],
                },
            )
            return result["hits"], result["estimatedTotalHits"]
        except MeilisearchApiError as e:
            logger.error(f"Search failed: {e}")
            return [], 0

    def search_producers(
        self,
        query: str,
        country: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Search producers by name."""
        if not self.client:
            return []

        filter_str = f'country = "{country}"' if country else None

        try:
            result = self.client.index(PRODUCERS_INDEX).search(
                query,
                {
                    "filter": filter_str,
                    "limit": limit,
                },
            )
            return result["hits"]
        except MeilisearchApiError as e:
            logger.error(f"Producer search failed: {e}")
            return []

    def search_regions(
        self,
        query: str,
        country: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Search regions by name."""
        if not self.client:
            return []

        filter_str = f'country = "{country}"' if country else None

        try:
            result = self.client.index(REGIONS_INDEX).search(
                query,
                {
                    "filter": filter_str,
                    "limit": limit,
                },
            )
            return result["hits"]
        except MeilisearchApiError as e:
            logger.error(f"Region search failed: {e}")
            return []

    # =========================================================================
    # Deletion Methods
    # =========================================================================

    def delete_vintage(self, vintage_id: UUID | str) -> None:
        """Delete a vintage from the index."""
        if not self.client:
            return

        try:
            self.client.index(WINES_INDEX).delete_document(str(vintage_id))
            logger.debug(f"Deleted vintage {vintage_id} from index")
        except MeilisearchApiError as e:
            logger.error(f"Failed to delete vintage {vintage_id}: {e}")

    def delete_producer(self, producer_id: UUID | str) -> None:
        """Delete a producer from the index."""
        if not self.client:
            return

        try:
            self.client.index(PRODUCERS_INDEX).delete_document(str(producer_id))
            logger.debug(f"Deleted producer {producer_id} from index")
        except MeilisearchApiError as e:
            logger.error(f"Failed to delete producer {producer_id}: {e}")

    def clear_all_indexes(self) -> None:
        """Clear all documents from all indexes (use with caution!)."""
        if not self.client:
            return

        for index_name in [WINES_INDEX, PRODUCERS_INDEX, REGIONS_INDEX]:
            try:
                self.client.index(index_name).delete_all_documents()
                logger.info(f"Cleared all documents from {index_name} index")
            except MeilisearchApiError as e:
                logger.error(f"Failed to clear {index_name} index: {e}")

    # =========================================================================
    # Stats Methods
    # =========================================================================

    def get_stats(self) -> dict[str, Any]:
        """Get statistics about all indexes."""
        if not self.client:
            return {"available": False}

        stats = {"available": True, "indexes": {}}

        for index_name in [WINES_INDEX, PRODUCERS_INDEX, REGIONS_INDEX]:
            try:
                index_stats = self.client.index(index_name).get_stats()
                stats["indexes"][index_name] = {
                    "numberOfDocuments": index_stats.number_of_documents,
                    "isIndexing": index_stats.is_indexing,
                }
            except MeilisearchApiError:
                stats["indexes"][index_name] = {"numberOfDocuments": 0, "isIndexing": False}

        return stats


# Singleton instance for convenience
_service_instance: MeilisearchService | None = None


def get_meilisearch_service() -> MeilisearchService:
    """Get or create the Meilisearch service instance."""
    global _service_instance
    if _service_instance is None:
        _service_instance = MeilisearchService()
    return _service_instance
