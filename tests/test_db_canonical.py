"""Tests for canonical entity database persistence layer."""

import tempfile
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from wine_agent.core.enums import WineColor, WineStyle
from wine_agent.core.schema_canonical import (
    Distributor,
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
    EntityType,
    MatchDecision,
    RegionHierarchyLevel,
    SnapshotStatus,
)
from wine_agent.db.models import Base
from wine_agent.db.models_canonical import (
    DistributorDB,
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
from wine_agent.db.repositories_canonical import (
    DistributorRepository,
    GrapeVarietyRepository,
    ImporterRepository,
    ListingMatchRepository,
    ListingRepository,
    ProducerRepository,
    RegionRepository,
    SnapshotRepository,
    SourceRepository,
    VintageRepository,
    WineRepository,
)


@pytest.fixture
def temp_db_path():
    """Create a temporary database file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir) / "test_canonical.db"


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


class TestProducerRepository:
    """Tests for ProducerRepository."""

    def test_create_producer(self, session: Session) -> None:
        """Test creating a producer."""
        repo = ProducerRepository(session)
        producer = Producer(
            canonical_name="Domaine de la Romanée-Conti",
            aliases=["DRC", "Romanée-Conti"],
            country="France",
            region="Burgundy",
        )

        created = repo.create(producer)
        session.commit()

        assert created.id == producer.id
        assert created.canonical_name == "Domaine de la Romanée-Conti"
        assert created.aliases == ["DRC", "Romanée-Conti"]
        assert created.country == "France"

    def test_get_producer_by_id(self, session: Session) -> None:
        """Test retrieving a producer by ID."""
        repo = ProducerRepository(session)
        producer = Producer(canonical_name="Ridge Vineyards", country="USA")
        repo.create(producer)
        session.commit()

        retrieved = repo.get_by_id(producer.id)

        assert retrieved is not None
        assert retrieved.canonical_name == "Ridge Vineyards"
        assert retrieved.country == "USA"

    def test_get_nonexistent_producer(self, session: Session) -> None:
        """Test retrieving a nonexistent producer."""
        repo = ProducerRepository(session)
        result = repo.get_by_id(uuid4())
        assert result is None

    def test_search_producers_by_name(self, session: Session) -> None:
        """Test searching producers by name."""
        repo = ProducerRepository(session)
        repo.create(Producer(canonical_name="Domaine Leflaive"))
        repo.create(Producer(canonical_name="Domaine Leroy"))
        repo.create(Producer(canonical_name="Ridge Vineyards"))
        session.commit()

        results = repo.search_by_name("Domaine")

        assert len(results) == 2
        names = [p.canonical_name for p in results]
        assert "Domaine Leflaive" in names
        assert "Domaine Leroy" in names

    def test_list_all_producers(self, session: Session) -> None:
        """Test listing all producers."""
        repo = ProducerRepository(session)
        repo.create(Producer(canonical_name="Producer A"))
        repo.create(Producer(canonical_name="Producer B"))
        repo.create(Producer(canonical_name="Producer C"))
        session.commit()

        results = repo.list_all(limit=2)

        assert len(results) == 2

    def test_count_producers(self, session: Session) -> None:
        """Test counting producers."""
        repo = ProducerRepository(session)
        assert repo.count() == 0

        repo.create(Producer(canonical_name="Producer 1"))
        repo.create(Producer(canonical_name="Producer 2"))
        session.commit()

        assert repo.count() == 2

    def test_update_producer(self, session: Session) -> None:
        """Test updating a producer."""
        repo = ProducerRepository(session)
        producer = Producer(canonical_name="Original Name")
        repo.create(producer)
        session.commit()

        producer.canonical_name = "Updated Name"
        producer.website = "https://example.com"
        updated = repo.update(producer)
        session.commit()

        retrieved = repo.get_by_id(producer.id)
        assert retrieved is not None
        assert retrieved.canonical_name == "Updated Name"
        assert retrieved.website == "https://example.com"

    def test_delete_producer(self, session: Session) -> None:
        """Test deleting a producer."""
        repo = ProducerRepository(session)
        producer = Producer(canonical_name="To Delete")
        repo.create(producer)
        session.commit()

        deleted = repo.delete(producer.id)
        session.commit()

        assert deleted is True
        assert repo.get_by_id(producer.id) is None


class TestWineRepository:
    """Tests for WineRepository."""

    def test_create_wine(self, session: Session) -> None:
        """Test creating a wine."""
        # First create a producer
        producer_repo = ProducerRepository(session)
        producer = Producer(canonical_name="Ridge Vineyards")
        producer_repo.create(producer)
        session.commit()

        wine_repo = WineRepository(session)
        wine = Wine(
            producer_id=producer.id,
            canonical_name="Monte Bello",
            color=WineColor.RED,
            style=WineStyle.STILL,
            grapes=["Cabernet Sauvignon", "Merlot"],
            appellation="Santa Cruz Mountains",
        )

        created = wine_repo.create(wine)
        session.commit()

        assert created.id == wine.id
        assert created.canonical_name == "Monte Bello"
        assert created.color == WineColor.RED
        assert created.grapes == ["Cabernet Sauvignon", "Merlot"]

    def test_get_wines_by_producer(self, session: Session) -> None:
        """Test getting wines by producer ID."""
        producer_repo = ProducerRepository(session)
        producer = Producer(canonical_name="Test Producer")
        producer_repo.create(producer)

        wine_repo = WineRepository(session)
        wine_repo.create(Wine(producer_id=producer.id, canonical_name="Wine A"))
        wine_repo.create(Wine(producer_id=producer.id, canonical_name="Wine B"))
        session.commit()

        wines = wine_repo.get_by_producer_id(producer.id)

        assert len(wines) == 2

    def test_search_wines_by_name(self, session: Session) -> None:
        """Test searching wines by name."""
        producer_repo = ProducerRepository(session)
        producer = Producer(canonical_name="Test Producer")
        producer_repo.create(producer)

        wine_repo = WineRepository(session)
        wine_repo.create(Wine(producer_id=producer.id, canonical_name="Cabernet Reserve"))
        wine_repo.create(Wine(producer_id=producer.id, canonical_name="Chardonnay"))
        wine_repo.create(Wine(producer_id=producer.id, canonical_name="Cabernet Franc"))
        session.commit()

        results = wine_repo.search_by_name("Cabernet")

        assert len(results) == 2


class TestVintageRepository:
    """Tests for VintageRepository."""

    def test_create_vintage(self, session: Session) -> None:
        """Test creating a vintage."""
        producer_repo = ProducerRepository(session)
        producer = Producer(canonical_name="Test Producer")
        producer_repo.create(producer)

        wine_repo = WineRepository(session)
        wine = Wine(producer_id=producer.id, canonical_name="Test Wine")
        wine_repo.create(wine)
        session.commit()

        vintage_repo = VintageRepository(session)
        vintage = Vintage(
            wine_id=wine.id,
            year=2019,
            bottle_size_ml=750,
            abv=13.5,
        )

        created = vintage_repo.create(vintage)
        session.commit()

        assert created.id == vintage.id
        assert created.year == 2019
        assert created.abv == 13.5

    def test_get_vintages_by_wine(self, session: Session) -> None:
        """Test getting vintages by wine ID."""
        producer_repo = ProducerRepository(session)
        producer = Producer(canonical_name="Test Producer")
        producer_repo.create(producer)

        wine_repo = WineRepository(session)
        wine = Wine(producer_id=producer.id, canonical_name="Test Wine")
        wine_repo.create(wine)

        vintage_repo = VintageRepository(session)
        vintage_repo.create(Vintage(wine_id=wine.id, year=2018))
        vintage_repo.create(Vintage(wine_id=wine.id, year=2019))
        vintage_repo.create(Vintage(wine_id=wine.id, year=2020))
        session.commit()

        vintages = vintage_repo.get_by_wine_id(wine.id)

        assert len(vintages) == 3
        # Should be ordered by year descending
        assert vintages[0].year == 2020
        assert vintages[1].year == 2019
        assert vintages[2].year == 2018

    def test_get_vintage_by_wine_and_year(self, session: Session) -> None:
        """Test getting a specific vintage by wine and year."""
        producer_repo = ProducerRepository(session)
        producer = Producer(canonical_name="Test Producer")
        producer_repo.create(producer)

        wine_repo = WineRepository(session)
        wine = Wine(producer_id=producer.id, canonical_name="Test Wine")
        wine_repo.create(wine)

        vintage_repo = VintageRepository(session)
        vintage_repo.create(Vintage(wine_id=wine.id, year=2019, abv=13.0))
        vintage_repo.create(Vintage(wine_id=wine.id, year=2020, abv=13.5))
        session.commit()

        found = vintage_repo.get_by_wine_and_year(wine.id, 2019)

        assert found is not None
        assert found.year == 2019
        assert found.abv == 13.0

        not_found = vintage_repo.get_by_wine_and_year(wine.id, 2018)
        assert not_found is None


class TestRegionRepository:
    """Tests for RegionRepository."""

    def test_create_region(self, session: Session) -> None:
        """Test creating a region."""
        repo = RegionRepository(session)
        region = Region(
            name="Burgundy",
            country="France",
            hierarchy_level=RegionHierarchyLevel.REGION,
        )

        created = repo.create(region)
        session.commit()

        assert created.name == "Burgundy"
        assert created.country == "France"

    def test_create_region_hierarchy(self, session: Session) -> None:
        """Test creating a region hierarchy."""
        repo = RegionRepository(session)

        # Create parent region
        parent = Region(
            name="Burgundy",
            country="France",
            hierarchy_level=RegionHierarchyLevel.REGION,
        )
        repo.create(parent)
        session.commit()

        # Create child region
        child = Region(
            name="Côte de Nuits",
            country="France",
            parent_id=parent.id,
            hierarchy_level=RegionHierarchyLevel.SUBREGION,
        )
        repo.create(child)
        session.commit()

        # Verify parent-child relationship
        children = repo.get_children(parent.id)
        assert len(children) == 1
        assert children[0].name == "Côte de Nuits"

    def test_search_regions_by_name(self, session: Session) -> None:
        """Test searching regions by name."""
        repo = RegionRepository(session)
        repo.create(Region(name="Burgundy", country="France"))
        repo.create(Region(name="Bordeaux", country="France"))
        repo.create(Region(name="Napa Valley", country="USA"))
        session.commit()

        results = repo.search_by_name("Bur")

        assert len(results) == 1
        assert results[0].name == "Burgundy"


class TestGrapeVarietyRepository:
    """Tests for GrapeVarietyRepository."""

    def test_create_grape(self, session: Session) -> None:
        """Test creating a grape variety."""
        repo = GrapeVarietyRepository(session)
        grape = GrapeVariety(
            canonical_name="Pinot Noir",
            aliases=["Pinot Nero", "Spätburgunder"],
            wikidata_id="Q36767",
        )

        created = repo.create(grape)
        session.commit()

        assert created.canonical_name == "Pinot Noir"
        assert created.aliases == ["Pinot Nero", "Spätburgunder"]

    def test_search_grapes_by_name(self, session: Session) -> None:
        """Test searching grapes by name."""
        repo = GrapeVarietyRepository(session)
        repo.create(GrapeVariety(canonical_name="Pinot Noir"))
        repo.create(GrapeVariety(canonical_name="Pinot Gris"))
        repo.create(GrapeVariety(canonical_name="Chardonnay"))
        session.commit()

        results = repo.search_by_name("Pinot")

        assert len(results) == 2


class TestSourceRepository:
    """Tests for SourceRepository."""

    def test_create_source(self, session: Session) -> None:
        """Test creating a source."""
        repo = SourceRepository(session)
        source = Source(
            domain="wine-searcher.com",
            adapter_type="json_ld",
            rate_limit_config={"requests_per_second": 0.5},
        )

        created = repo.create(source)
        session.commit()

        assert created.domain == "wine-searcher.com"
        assert created.adapter_type == "json_ld"
        assert created.enabled is True

    def test_get_source_by_domain(self, session: Session) -> None:
        """Test getting a source by domain."""
        repo = SourceRepository(session)
        repo.create(Source(domain="example.com", adapter_type="html"))
        session.commit()

        found = repo.get_by_domain("example.com")

        assert found is not None
        assert found.domain == "example.com"

    def test_list_enabled_sources(self, session: Session) -> None:
        """Test listing enabled sources."""
        repo = SourceRepository(session)
        repo.create(Source(domain="enabled1.com", adapter_type="html", enabled=True))
        repo.create(Source(domain="disabled.com", adapter_type="html", enabled=False))
        repo.create(Source(domain="enabled2.com", adapter_type="html", enabled=True))
        session.commit()

        enabled = repo.list_enabled()

        assert len(enabled) == 2
        domains = [s.domain for s in enabled]
        assert "disabled.com" not in domains


class TestSnapshotRepository:
    """Tests for SnapshotRepository."""

    def test_create_snapshot(self, session: Session) -> None:
        """Test creating a snapshot."""
        source_repo = SourceRepository(session)
        source = Source(domain="example.com", adapter_type="html")
        source_repo.create(source)
        session.commit()

        snapshot_repo = SnapshotRepository(session)
        snapshot = Snapshot(
            source_id=source.id,
            url="https://example.com/wine/123",
            content_hash="abc123",
            file_path="/snapshots/abc123.html",
        )

        created = snapshot_repo.create(snapshot)
        session.commit()

        assert created.content_hash == "abc123"
        assert created.status == SnapshotStatus.PENDING

    def test_get_snapshot_by_hash(self, session: Session) -> None:
        """Test getting a snapshot by content hash (deduplication)."""
        source_repo = SourceRepository(session)
        source = Source(domain="example.com", adapter_type="html")
        source_repo.create(source)

        snapshot_repo = SnapshotRepository(session)
        snapshot_repo.create(Snapshot(
            source_id=source.id,
            url="https://example.com/wine/123",
            content_hash="unique_hash",
        ))
        session.commit()

        found = snapshot_repo.get_by_content_hash("unique_hash")

        assert found is not None
        assert found.url == "https://example.com/wine/123"


class TestListingRepository:
    """Tests for ListingRepository."""

    def test_create_listing(self, session: Session) -> None:
        """Test creating a listing."""
        source_repo = SourceRepository(session)
        source = Source(domain="example.com", adapter_type="html")
        source_repo.create(source)

        snapshot_repo = SnapshotRepository(session)
        snapshot = Snapshot(
            source_id=source.id,
            url="https://example.com/wine/123",
            content_hash="hash",
        )
        snapshot_repo.create(snapshot)
        session.commit()

        listing_repo = ListingRepository(session)
        listing = Listing(
            source_id=source.id,
            snapshot_id=snapshot.id,
            url="https://example.com/wine/123",
            title="Ridge Monte Bello 2019",
            upc="012345678901",
            price=199.99,
        )

        created = listing_repo.create(listing)
        session.commit()

        assert created.title == "Ridge Monte Bello 2019"
        assert created.upc == "012345678901"
        assert created.price == 199.99

    def test_get_listings_by_upc(self, session: Session) -> None:
        """Test getting listings by UPC code."""
        source_repo = SourceRepository(session)
        source = Source(domain="example.com", adapter_type="html")
        source_repo.create(source)

        snapshot_repo = SnapshotRepository(session)
        snapshot = Snapshot(source_id=source.id, url="url", content_hash="hash")
        snapshot_repo.create(snapshot)
        session.commit()

        listing_repo = ListingRepository(session)
        listing_repo.create(Listing(
            source_id=source.id,
            snapshot_id=snapshot.id,
            url="url1",
            upc="123456789012",
        ))
        listing_repo.create(Listing(
            source_id=source.id,
            snapshot_id=snapshot.id,
            url="url2",
            upc="123456789012",  # Same UPC
        ))
        session.commit()

        results = listing_repo.get_by_upc("123456789012")

        assert len(results) == 2


class TestListingMatchRepository:
    """Tests for ListingMatchRepository."""

    def test_create_listing_match(self, session: Session) -> None:
        """Test creating a listing match."""
        source_repo = SourceRepository(session)
        source = Source(domain="example.com", adapter_type="html")
        source_repo.create(source)

        snapshot_repo = SnapshotRepository(session)
        snapshot = Snapshot(source_id=source.id, url="url", content_hash="hash")
        snapshot_repo.create(snapshot)

        listing_repo = ListingRepository(session)
        listing = Listing(source_id=source.id, snapshot_id=snapshot.id, url="url")
        listing_repo.create(listing)
        session.commit()

        match_repo = ListingMatchRepository(session)
        vintage_id = uuid4()
        match = ListingMatch(
            listing_id=listing.id,
            entity_type=EntityType.VINTAGE,
            entity_id=vintage_id,
            confidence=0.95,
            decision=MatchDecision.AUTO,
        )

        created = match_repo.create(match)
        session.commit()

        assert created.confidence == 0.95
        assert created.entity_type == EntityType.VINTAGE

    def test_get_pending_review_matches(self, session: Session) -> None:
        """Test getting matches pending manual review."""
        source_repo = SourceRepository(session)
        source = Source(domain="example.com", adapter_type="html")
        source_repo.create(source)

        snapshot_repo = SnapshotRepository(session)
        snapshot = Snapshot(source_id=source.id, url="url", content_hash="hash")
        snapshot_repo.create(snapshot)

        listing_repo = ListingRepository(session)
        listing = Listing(source_id=source.id, snapshot_id=snapshot.id, url="url")
        listing_repo.create(listing)
        session.commit()

        match_repo = ListingMatchRepository(session)
        # High confidence - auto-approved
        match_repo.create(ListingMatch(
            listing_id=listing.id,
            entity_type=EntityType.WINE,
            entity_id=uuid4(),
            confidence=0.95,
        ))
        # Medium confidence - needs review
        match_repo.create(ListingMatch(
            listing_id=listing.id,
            entity_type=EntityType.WINE,
            entity_id=uuid4(),
            confidence=0.80,
        ))
        # Low confidence - not auto-matched
        match_repo.create(ListingMatch(
            listing_id=listing.id,
            entity_type=EntityType.WINE,
            entity_id=uuid4(),
            confidence=0.60,
        ))
        session.commit()

        pending = match_repo.get_pending_review(min_confidence=0.7, max_confidence=0.9)

        assert len(pending) == 1
        assert pending[0].confidence == 0.80


class TestFullCanonicalWorkflow:
    """Integration tests for the full canonical entity workflow."""

    def test_producer_wine_vintage_creation(self, session: Session) -> None:
        """Test creating a complete producer -> wine -> vintage hierarchy."""
        producer_repo = ProducerRepository(session)
        wine_repo = WineRepository(session)
        vintage_repo = VintageRepository(session)

        # Create producer
        producer = Producer(
            canonical_name="Domaine de la Romanée-Conti",
            aliases=["DRC"],
            country="France",
            region="Burgundy",
        )
        producer_repo.create(producer)

        # Create wines for the producer
        wine1 = Wine(
            producer_id=producer.id,
            canonical_name="Romanée-Conti",
            color=WineColor.RED,
            grapes=["Pinot Noir"],
            appellation="Romanée-Conti AOC",
        )
        wine2 = Wine(
            producer_id=producer.id,
            canonical_name="La Tâche",
            color=WineColor.RED,
            grapes=["Pinot Noir"],
            appellation="La Tâche AOC",
        )
        wine_repo.create(wine1)
        wine_repo.create(wine2)

        # Create vintages for the first wine
        for year in [2018, 2019, 2020]:
            vintage_repo.create(Vintage(
                wine_id=wine1.id,
                year=year,
                bottle_size_ml=750,
            ))

        session.commit()

        # Verify the hierarchy
        retrieved_producer = producer_repo.get_by_id(producer.id)
        assert retrieved_producer is not None

        wines = wine_repo.get_by_producer_id(producer.id)
        assert len(wines) == 2

        vintages = vintage_repo.get_by_wine_id(wine1.id)
        assert len(vintages) == 3

        # Verify counts
        assert producer_repo.count() == 1
        assert wine_repo.count() == 2
        assert vintage_repo.count() == 3
