"""Tests for catalog service."""

import tempfile
from pathlib import Path
from uuid import uuid4
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from wine_agent.core.enums import WineColor, WineStyle
from wine_agent.core.schema_canonical import (
    CatalogSearchRequest,
    Producer,
    Region,
    Vintage,
    Wine,
    RegionHierarchyLevel,
)
from wine_agent.db.models import Base
from wine_agent.services.catalog_service import CatalogService


@pytest.fixture
def temp_db_path():
    """Create a temporary database file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir) / "test_catalog.db"


@pytest.fixture
def engine(temp_db_path):
    """Create a test database engine."""
    url = f"sqlite:///{temp_db_path}"
    engine = create_engine(url, echo=False)
    # Import canonical models to register them with Base
    from wine_agent.db import models_canonical  # noqa: F401
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def session(engine):
    """Create a database session for testing."""
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def mock_meilisearch():
    """Create a mock Meilisearch service."""
    mock = MagicMock()
    mock.is_available.return_value = False  # Disable actual Meilisearch calls
    mock.index_producer.return_value = None
    mock.index_wine_without_vintage.return_value = None
    mock.index_wine_vintage.return_value = None
    mock.index_region.return_value = None
    mock.search_wines.return_value = ([], 0)
    mock.get_stats.return_value = {"available": False}
    return mock


@pytest.fixture
def catalog_service(session, mock_meilisearch):
    """Create a catalog service with mocked Meilisearch."""
    return CatalogService(session=session, meilisearch=mock_meilisearch)


class TestProducerOperations:
    """Tests for producer operations in catalog service."""

    def test_create_producer(self, catalog_service: CatalogService) -> None:
        """Test creating a producer."""
        producer = catalog_service.create_producer(
            canonical_name="Ridge Vineyards",
            country="USA",
            region="California",
            aliases=["Ridge"],
            website="https://ridgewine.com",
        )

        assert producer.canonical_name == "Ridge Vineyards"
        assert producer.country == "USA"
        assert producer.aliases == ["Ridge"]

    def test_get_producer(self, catalog_service: CatalogService) -> None:
        """Test getting a producer by ID."""
        created = catalog_service.create_producer(
            canonical_name="Test Producer"
        )

        retrieved = catalog_service.get_producer(created.id)

        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.canonical_name == "Test Producer"

    def test_search_producers(self, catalog_service: CatalogService) -> None:
        """Test searching producers."""
        catalog_service.create_producer(canonical_name="Domaine Leflaive")
        catalog_service.create_producer(canonical_name="Domaine Leroy")
        catalog_service.create_producer(canonical_name="Ridge Vineyards")

        results = catalog_service.search_producers("Domaine")

        assert len(results) == 2

    def test_update_producer(self, catalog_service: CatalogService) -> None:
        """Test updating a producer."""
        producer = catalog_service.create_producer(
            canonical_name="Original Name"
        )

        producer.canonical_name = "Updated Name"
        producer.website = "https://updated.com"
        updated = catalog_service.update_producer(producer)

        assert updated.canonical_name == "Updated Name"
        assert updated.website == "https://updated.com"


class TestWineOperations:
    """Tests for wine operations in catalog service."""

    def test_create_wine(self, catalog_service: CatalogService) -> None:
        """Test creating a wine."""
        producer = catalog_service.create_producer(canonical_name="Ridge Vineyards")

        wine = catalog_service.create_wine(
            producer_id=producer.id,
            canonical_name="Monte Bello",
            color="red",
            style="still",
            grapes=["Cabernet Sauvignon", "Merlot"],
            appellation="Santa Cruz Mountains",
        )

        assert wine.canonical_name == "Monte Bello"
        assert wine.color == WineColor.RED
        assert wine.grapes == ["Cabernet Sauvignon", "Merlot"]

    def test_get_wine(self, catalog_service: CatalogService) -> None:
        """Test getting a wine by ID."""
        producer = catalog_service.create_producer(canonical_name="Test Producer")
        created = catalog_service.create_wine(
            producer_id=producer.id,
            canonical_name="Test Wine"
        )

        retrieved = catalog_service.get_wine(created.id)

        assert retrieved is not None
        assert retrieved.canonical_name == "Test Wine"

    def test_get_wines_by_producer(self, catalog_service: CatalogService) -> None:
        """Test getting wines by producer."""
        producer = catalog_service.create_producer(canonical_name="Test Producer")
        catalog_service.create_wine(producer_id=producer.id, canonical_name="Wine A")
        catalog_service.create_wine(producer_id=producer.id, canonical_name="Wine B")

        wines = catalog_service.get_wines_by_producer(producer.id)

        assert len(wines) == 2

    def test_search_wines(self, catalog_service: CatalogService) -> None:
        """Test searching wines."""
        producer = catalog_service.create_producer(canonical_name="Test Producer")
        catalog_service.create_wine(producer_id=producer.id, canonical_name="Cabernet Reserve")
        catalog_service.create_wine(producer_id=producer.id, canonical_name="Chardonnay")

        results = catalog_service.search_wines("Cabernet")

        assert len(results) == 1
        assert results[0].canonical_name == "Cabernet Reserve"


class TestVintageOperations:
    """Tests for vintage operations in catalog service."""

    def test_create_vintage(self, catalog_service: CatalogService) -> None:
        """Test creating a vintage."""
        producer = catalog_service.create_producer(canonical_name="Test Producer")
        wine = catalog_service.create_wine(
            producer_id=producer.id,
            canonical_name="Test Wine"
        )

        vintage = catalog_service.create_vintage(
            wine_id=wine.id,
            year=2019,
            bottle_size_ml=750,
            abv=13.5,
        )

        assert vintage.year == 2019
        assert vintage.abv == 13.5

    def test_get_vintage(self, catalog_service: CatalogService) -> None:
        """Test getting a vintage by ID."""
        producer = catalog_service.create_producer(canonical_name="Test Producer")
        wine = catalog_service.create_wine(producer_id=producer.id, canonical_name="Test Wine")
        created = catalog_service.create_vintage(wine_id=wine.id, year=2020)

        retrieved = catalog_service.get_vintage(created.id)

        assert retrieved is not None
        assert retrieved.year == 2020

    def test_get_vintages_by_wine(self, catalog_service: CatalogService) -> None:
        """Test getting vintages by wine."""
        producer = catalog_service.create_producer(canonical_name="Test Producer")
        wine = catalog_service.create_wine(producer_id=producer.id, canonical_name="Test Wine")
        catalog_service.create_vintage(wine_id=wine.id, year=2018)
        catalog_service.create_vintage(wine_id=wine.id, year=2019)
        catalog_service.create_vintage(wine_id=wine.id, year=2020)

        vintages = catalog_service.get_vintages_by_wine(wine.id)

        assert len(vintages) == 3
        # Should be ordered by year descending
        assert vintages[0].year == 2020

    def test_get_or_create_vintage_existing(self, catalog_service: CatalogService) -> None:
        """Test get_or_create returns existing vintage."""
        producer = catalog_service.create_producer(canonical_name="Test Producer")
        wine = catalog_service.create_wine(producer_id=producer.id, canonical_name="Test Wine")
        existing = catalog_service.create_vintage(wine_id=wine.id, year=2019, abv=13.0)

        vintage, created = catalog_service.get_or_create_vintage(
            wine_id=wine.id,
            year=2019,
            abv=14.0,  # Different ABV, should still return existing
        )

        assert created is False
        assert vintage.id == existing.id
        assert vintage.abv == 13.0  # Original ABV preserved

    def test_get_or_create_vintage_new(self, catalog_service: CatalogService) -> None:
        """Test get_or_create creates new vintage when not found."""
        producer = catalog_service.create_producer(canonical_name="Test Producer")
        wine = catalog_service.create_wine(producer_id=producer.id, canonical_name="Test Wine")

        vintage, created = catalog_service.get_or_create_vintage(
            wine_id=wine.id,
            year=2019,
            abv=13.5,
        )

        assert created is True
        assert vintage.year == 2019
        assert vintage.abv == 13.5


class TestRegionOperations:
    """Tests for region operations in catalog service."""

    def test_create_region(self, catalog_service: CatalogService) -> None:
        """Test creating a region."""
        region = catalog_service.create_region(
            name="Burgundy",
            country="France",
            hierarchy_level="region",
        )

        assert region.name == "Burgundy"
        assert region.country == "France"
        assert region.hierarchy_level == RegionHierarchyLevel.REGION

    def test_get_region(self, catalog_service: CatalogService) -> None:
        """Test getting a region by ID."""
        created = catalog_service.create_region(name="Test Region")

        retrieved = catalog_service.get_region(created.id)

        assert retrieved is not None
        assert retrieved.name == "Test Region"

    def test_search_regions(self, catalog_service: CatalogService) -> None:
        """Test searching regions."""
        catalog_service.create_region(name="Burgundy", country="France")
        catalog_service.create_region(name="Bordeaux", country="France")
        catalog_service.create_region(name="Barossa Valley", country="Australia")

        results = catalog_service.search_regions("Bur")

        assert len(results) == 1
        assert results[0].name == "Burgundy"


class TestGrapeVarietyOperations:
    """Tests for grape variety operations in catalog service."""

    def test_create_grape_variety(self, catalog_service: CatalogService) -> None:
        """Test creating a grape variety."""
        grape = catalog_service.create_grape_variety(
            canonical_name="Pinot Noir",
            aliases=["Pinot Nero", "Spätburgunder"],
        )

        assert grape.canonical_name == "Pinot Noir"
        assert grape.aliases == ["Pinot Nero", "Spätburgunder"]

    def test_get_grape_variety(self, catalog_service: CatalogService) -> None:
        """Test getting a grape variety by ID."""
        created = catalog_service.create_grape_variety(canonical_name="Chardonnay")

        retrieved = catalog_service.get_grape_variety(created.id)

        assert retrieved is not None
        assert retrieved.canonical_name == "Chardonnay"

    def test_search_grape_varieties(self, catalog_service: CatalogService) -> None:
        """Test searching grape varieties."""
        catalog_service.create_grape_variety(canonical_name="Pinot Noir")
        catalog_service.create_grape_variety(canonical_name="Pinot Gris")
        catalog_service.create_grape_variety(canonical_name="Chardonnay")

        results = catalog_service.search_grape_varieties("Pinot")

        assert len(results) == 2


class TestCatalogStats:
    """Tests for catalog statistics."""

    def test_get_catalog_stats_empty(self, catalog_service: CatalogService) -> None:
        """Test getting stats for empty catalog."""
        stats = catalog_service.get_catalog_stats()

        assert stats.total_producers == 0
        assert stats.total_wines == 0
        assert stats.total_vintages == 0

    def test_get_catalog_stats_with_data(self, catalog_service: CatalogService) -> None:
        """Test getting stats with data in catalog."""
        # Create some entities
        producer = catalog_service.create_producer(canonical_name="Test Producer")
        wine1 = catalog_service.create_wine(producer_id=producer.id, canonical_name="Wine 1")
        wine2 = catalog_service.create_wine(producer_id=producer.id, canonical_name="Wine 2")
        catalog_service.create_vintage(wine_id=wine1.id, year=2019)
        catalog_service.create_vintage(wine_id=wine1.id, year=2020)
        catalog_service.create_region(name="Test Region")
        catalog_service.create_grape_variety(canonical_name="Test Grape")

        stats = catalog_service.get_catalog_stats()

        assert stats.total_producers == 1
        assert stats.total_wines == 2
        assert stats.total_vintages == 2
        assert stats.total_regions == 1
        assert stats.total_grapes == 1


class TestFullCatalogWorkflow:
    """Integration tests for full catalog workflow."""

    def test_complete_wine_creation_workflow(self, catalog_service: CatalogService) -> None:
        """Test creating a complete wine entry from producer to vintage."""
        # Create region first
        region = catalog_service.create_region(
            name="Santa Cruz Mountains",
            country="USA",
            hierarchy_level="appellation",
        )

        # Create grape varieties
        cab = catalog_service.create_grape_variety(
            canonical_name="Cabernet Sauvignon",
            aliases=["Cab Sauv", "Cabernet"],
        )
        merlot = catalog_service.create_grape_variety(canonical_name="Merlot")

        # Create producer
        producer = catalog_service.create_producer(
            canonical_name="Ridge Vineyards",
            country="USA",
            region="California",
            website="https://ridgewine.com",
        )

        # Create wine
        wine = catalog_service.create_wine(
            producer_id=producer.id,
            canonical_name="Monte Bello",
            color="red",
            style="still",
            grapes=["Cabernet Sauvignon", "Merlot", "Petit Verdot"],
            appellation="Santa Cruz Mountains",
            region_id=region.id,
        )

        # Create vintages
        vintages = []
        for year in [2018, 2019, 2020]:
            v = catalog_service.create_vintage(
                wine_id=wine.id,
                year=year,
                abv=13.5 + (year - 2018) * 0.1,
            )
            vintages.append(v)

        # Verify everything was created
        retrieved_producer = catalog_service.get_producer(producer.id)
        assert retrieved_producer is not None
        assert retrieved_producer.canonical_name == "Ridge Vineyards"

        wines = catalog_service.get_wines_by_producer(producer.id)
        assert len(wines) == 1
        assert wines[0].canonical_name == "Monte Bello"

        wine_vintages = catalog_service.get_vintages_by_wine(wine.id)
        assert len(wine_vintages) == 3

        # Check stats
        stats = catalog_service.get_catalog_stats()
        assert stats.total_producers == 1
        assert stats.total_wines == 1
        assert stats.total_vintages == 3
        assert stats.total_regions == 1
        assert stats.total_grapes == 2
