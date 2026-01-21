"""Tests for Meilisearch service."""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from wine_agent.core.enums import WineColor, WineStyle
from wine_agent.core.schema_canonical import (
    CatalogSearchRequest,
    Producer,
    Region,
    Vintage,
    Wine,
    RegionHierarchyLevel,
)
from wine_agent.services.meilisearch_service import (
    MeilisearchService,
    WINES_INDEX,
    PRODUCERS_INDEX,
    REGIONS_INDEX,
)


@pytest.fixture
def mock_meilisearch_client():
    """Create a mock Meilisearch client."""
    mock_client = MagicMock()
    mock_client.health.return_value = True

    # Mock index
    mock_index = MagicMock()
    mock_index.add_documents.return_value = None
    mock_index.search.return_value = {"hits": [], "estimatedTotalHits": 0}
    mock_index.update_settings.return_value = None
    mock_index.get_stats.return_value = MagicMock(
        number_of_documents=0,
        is_indexing=False
    )
    mock_index.delete_document.return_value = None
    mock_index.delete_all_documents.return_value = None

    mock_client.index.return_value = mock_index

    return mock_client


@pytest.fixture
def meilisearch_service(mock_meilisearch_client):
    """Create a MeilisearchService with mocked client."""
    with patch("wine_agent.services.meilisearch_service.Client") as MockClient:
        MockClient.return_value = mock_meilisearch_client
        with patch("wine_agent.services.meilisearch_service.MEILISEARCH_AVAILABLE", True):
            service = MeilisearchService(url="http://localhost:7700")
            service.client = mock_meilisearch_client
            return service


class TestMeilisearchServiceAvailability:
    """Tests for Meilisearch service availability."""

    def test_is_available_when_connected(self, meilisearch_service):
        """Test is_available returns True when connected."""
        meilisearch_service.client.health.return_value = True
        assert meilisearch_service.is_available() is True

    def test_is_available_when_not_connected(self, meilisearch_service):
        """Test is_available returns False when not connected."""
        meilisearch_service.client.health.side_effect = Exception("Connection error")
        assert meilisearch_service.is_available() is False

    def test_is_available_when_no_client(self):
        """Test is_available returns False when no client."""
        service = MeilisearchService.__new__(MeilisearchService)
        service.client = None
        assert service.is_available() is False


class TestIndexSetup:
    """Tests for index setup."""

    def test_setup_indexes(self, meilisearch_service):
        """Test setting up Meilisearch indexes."""
        meilisearch_service.setup_indexes()

        # Verify index was called for each index type
        calls = meilisearch_service.client.index.call_args_list
        index_names = [call[0][0] for call in calls]

        assert WINES_INDEX in index_names
        assert PRODUCERS_INDEX in index_names
        assert REGIONS_INDEX in index_names


class TestProducerIndexing:
    """Tests for producer indexing."""

    def test_index_producer(self, meilisearch_service):
        """Test indexing a producer."""
        producer = Producer(
            id=uuid4(),
            canonical_name="Ridge Vineyards",
            aliases=["Ridge"],
            country="USA",
            region="California",
        )

        meilisearch_service.index_producer(producer)

        # Verify add_documents was called
        index = meilisearch_service.client.index(PRODUCERS_INDEX)
        index.add_documents.assert_called_once()

        # Verify document structure
        call_args = index.add_documents.call_args[0][0]
        assert len(call_args) == 1
        doc = call_args[0]
        assert doc["canonical_name"] == "Ridge Vineyards"
        assert doc["aliases"] == ["Ridge"]
        assert doc["country"] == "USA"


class TestWineVintageIndexing:
    """Tests for wine/vintage indexing."""

    def test_index_wine_vintage(self, meilisearch_service):
        """Test indexing a wine vintage."""
        producer = Producer(
            id=uuid4(),
            canonical_name="Ridge Vineyards",
            aliases=["Ridge"],
            country="USA",
        )
        wine = Wine(
            id=uuid4(),
            producer_id=producer.id,
            canonical_name="Monte Bello",
            color=WineColor.RED,
            style=WineStyle.STILL,
            grapes=["Cabernet Sauvignon"],
            appellation="Santa Cruz Mountains",
        )
        vintage = Vintage(
            id=uuid4(),
            wine_id=wine.id,
            year=2019,
            abv=13.5,
        )

        meilisearch_service.index_wine_vintage(vintage, wine, producer)

        # Verify add_documents was called
        index = meilisearch_service.client.index(WINES_INDEX)
        index.add_documents.assert_called_once()

        # Verify document structure
        call_args = index.add_documents.call_args[0][0]
        doc = call_args[0]
        assert doc["wine_name"] == "Monte Bello"
        assert doc["producer_name"] == "Ridge Vineyards"
        assert doc["year"] == 2019
        assert doc["color"] == "red"

    def test_index_wine_vintage_with_region(self, meilisearch_service):
        """Test indexing a wine vintage with region."""
        producer = Producer(id=uuid4(), canonical_name="Test Producer")
        region = Region(
            id=uuid4(),
            name="Santa Cruz Mountains",
            country="USA",
            hierarchy_level=RegionHierarchyLevel.APPELLATION,
        )
        wine = Wine(
            id=uuid4(),
            producer_id=producer.id,
            canonical_name="Test Wine",
            region_id=region.id,
        )
        vintage = Vintage(id=uuid4(), wine_id=wine.id, year=2020)

        meilisearch_service.index_wine_vintage(vintage, wine, producer, region)

        index = meilisearch_service.client.index(WINES_INDEX)
        call_args = index.add_documents.call_args[0][0]
        doc = call_args[0]
        assert doc["region_name"] == "Santa Cruz Mountains"
        assert doc["region_id"] == str(region.id)

    def test_index_wine_without_vintage(self, meilisearch_service):
        """Test indexing a wine without a specific vintage."""
        producer = Producer(id=uuid4(), canonical_name="Test Producer", country="France")
        wine = Wine(
            id=uuid4(),
            producer_id=producer.id,
            canonical_name="NV Champagne",
            style=WineStyle.SPARKLING,
        )

        meilisearch_service.index_wine_without_vintage(wine, producer)

        index = meilisearch_service.client.index(WINES_INDEX)
        index.add_documents.assert_called_once()

        call_args = index.add_documents.call_args[0][0]
        doc = call_args[0]
        assert doc["wine_name"] == "NV Champagne"
        assert doc["year"] is None
        assert doc["vintage_id"] is None


class TestRegionIndexing:
    """Tests for region indexing."""

    def test_index_region(self, meilisearch_service):
        """Test indexing a region."""
        region = Region(
            id=uuid4(),
            name="Burgundy",
            aliases=["Bourgogne"],
            country="France",
            hierarchy_level=RegionHierarchyLevel.REGION,
        )

        meilisearch_service.index_region(region)

        index = meilisearch_service.client.index(REGIONS_INDEX)
        index.add_documents.assert_called_once()

        call_args = index.add_documents.call_args[0][0]
        doc = call_args[0]
        assert doc["name"] == "Burgundy"
        assert doc["aliases"] == ["Bourgogne"]
        assert doc["country"] == "France"


class TestBulkIndexing:
    """Tests for bulk indexing."""

    def test_bulk_index_wines(self, meilisearch_service):
        """Test bulk indexing wines."""
        documents = [
            {"id": str(uuid4()), "wine_name": "Wine 1"},
            {"id": str(uuid4()), "wine_name": "Wine 2"},
            {"id": str(uuid4()), "wine_name": "Wine 3"},
        ]

        meilisearch_service.bulk_index_wines(documents)

        index = meilisearch_service.client.index(WINES_INDEX)
        index.add_documents.assert_called_once_with(documents)

    def test_bulk_index_empty_list(self, meilisearch_service):
        """Test bulk indexing with empty list does nothing."""
        meilisearch_service.bulk_index_wines([])

        index = meilisearch_service.client.index(WINES_INDEX)
        index.add_documents.assert_not_called()

    def test_bulk_index_producers(self, meilisearch_service):
        """Test bulk indexing producers."""
        documents = [
            {"id": str(uuid4()), "canonical_name": "Producer 1"},
            {"id": str(uuid4()), "canonical_name": "Producer 2"},
        ]

        meilisearch_service.bulk_index_producers(documents)

        index = meilisearch_service.client.index(PRODUCERS_INDEX)
        index.add_documents.assert_called_once_with(documents)


class TestWineSearch:
    """Tests for wine search."""

    def test_search_wines_basic(self, meilisearch_service):
        """Test basic wine search."""
        mock_index = meilisearch_service.client.index(WINES_INDEX)
        mock_index.search.return_value = {
            "hits": [
                {"id": "1", "wine_name": "Monte Bello", "producer_name": "Ridge"},
                {"id": "2", "wine_name": "Monte Bello", "producer_name": "Other"},
            ],
            "estimatedTotalHits": 2,
        }

        request = CatalogSearchRequest(query="Monte Bello")
        results, total = meilisearch_service.search_wines(request)

        assert len(results) == 2
        assert total == 2
        mock_index.search.assert_called_once()

    def test_search_wines_with_filters(self, meilisearch_service):
        """Test wine search with filters."""
        mock_index = meilisearch_service.client.index(WINES_INDEX)
        mock_index.search.return_value = {"hits": [], "estimatedTotalHits": 0}

        request = CatalogSearchRequest(
            query="Pinot",
            country="France",
            vintage_year=2019,
            region="Burgundy",
        )
        results, total = meilisearch_service.search_wines(request)

        # Verify filter string was constructed
        # search() is called with (query, {options_dict}) as positional args
        call_args = mock_index.search.call_args
        options = call_args[0][1]  # Second positional argument is the options dict
        assert options["filter"] is not None
        filter_str = options["filter"]
        assert 'country = "France"' in filter_str
        assert "year = 2019" in filter_str
        assert 'region_name = "Burgundy"' in filter_str

    def test_search_wines_pagination(self, meilisearch_service):
        """Test wine search with pagination."""
        mock_index = meilisearch_service.client.index(WINES_INDEX)
        mock_index.search.return_value = {"hits": [], "estimatedTotalHits": 100}

        request = CatalogSearchRequest(query="", page=3, page_size=10)
        meilisearch_service.search_wines(request)

        # search() is called with (query, {options_dict}) as positional args
        call_args = mock_index.search.call_args
        options = call_args[0][1]  # Second positional argument is the options dict
        assert options["limit"] == 10
        assert options["offset"] == 20  # (page 3 - 1) * 10


class TestProducerSearch:
    """Tests for producer search."""

    def test_search_producers(self, meilisearch_service):
        """Test producer search."""
        mock_index = meilisearch_service.client.index(PRODUCERS_INDEX)
        mock_index.search.return_value = {
            "hits": [
                {"id": "1", "canonical_name": "Domaine Leflaive"},
            ],
            "estimatedTotalHits": 1,
        }

        results = meilisearch_service.search_producers("Domaine")

        assert len(results) == 1
        assert results[0]["canonical_name"] == "Domaine Leflaive"

    def test_search_producers_with_country_filter(self, meilisearch_service):
        """Test producer search with country filter."""
        mock_index = meilisearch_service.client.index(PRODUCERS_INDEX)
        mock_index.search.return_value = {"hits": [], "estimatedTotalHits": 0}

        meilisearch_service.search_producers("Ridge", country="USA")

        # search() is called with (query, {options_dict}) as positional args
        call_args = mock_index.search.call_args
        options = call_args[0][1]  # Second positional argument is the options dict
        assert options["filter"] == 'country = "USA"'


class TestRegionSearch:
    """Tests for region search."""

    def test_search_regions(self, meilisearch_service):
        """Test region search."""
        mock_index = meilisearch_service.client.index(REGIONS_INDEX)
        mock_index.search.return_value = {
            "hits": [
                {"id": "1", "name": "Burgundy"},
            ],
            "estimatedTotalHits": 1,
        }

        results = meilisearch_service.search_regions("Burg")

        assert len(results) == 1
        assert results[0]["name"] == "Burgundy"


class TestDeletion:
    """Tests for deletion operations."""

    def test_delete_vintage(self, meilisearch_service):
        """Test deleting a vintage from index."""
        vintage_id = uuid4()

        meilisearch_service.delete_vintage(vintage_id)

        index = meilisearch_service.client.index(WINES_INDEX)
        index.delete_document.assert_called_once_with(str(vintage_id))

    def test_delete_producer(self, meilisearch_service):
        """Test deleting a producer from index."""
        producer_id = uuid4()

        meilisearch_service.delete_producer(producer_id)

        index = meilisearch_service.client.index(PRODUCERS_INDEX)
        index.delete_document.assert_called_once_with(str(producer_id))

    def test_clear_all_indexes(self, meilisearch_service):
        """Test clearing all indexes."""
        meilisearch_service.clear_all_indexes()

        # Should delete all documents from all 3 indexes
        assert meilisearch_service.client.index.call_count >= 3


class TestStats:
    """Tests for stats retrieval."""

    def test_get_stats(self, meilisearch_service):
        """Test getting index statistics."""
        mock_stats = MagicMock()
        mock_stats.number_of_documents = 100
        mock_stats.is_indexing = False

        mock_index = meilisearch_service.client.index.return_value
        mock_index.get_stats.return_value = mock_stats

        stats = meilisearch_service.get_stats()

        assert stats["available"] is True
        assert "indexes" in stats


class TestNoClientScenarios:
    """Tests for scenarios when client is not available."""

    def test_operations_when_no_client(self):
        """Test that operations gracefully handle no client."""
        service = MeilisearchService.__new__(MeilisearchService)
        service.client = None

        # These should not raise exceptions
        service.index_producer(Producer(canonical_name="Test"))
        service.index_region(Region(name="Test"))

        results, total = service.search_wines(CatalogSearchRequest())
        assert results == []
        assert total == 0

        stats = service.get_stats()
        assert stats["available"] is False
