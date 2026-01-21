"""Tests for canonical entity Pydantic models."""

import pytest
from uuid import uuid4
from datetime import datetime, UTC

from wine_agent.core.schema_canonical import (
    Producer,
    Wine,
    Vintage,
    Region,
    GrapeVariety,
    Importer,
    Distributor,
    Source,
    Snapshot,
    Listing,
    ListingMatch,
    FieldProvenance,
    CatalogSearchRequest,
    CatalogStats,
    EntityType,
    MatchDecision,
    SnapshotStatus,
    RegionHierarchyLevel,
)
from wine_agent.core.enums import WineColor, WineStyle


class TestProducerModel:
    """Tests for Producer Pydantic model."""

    def test_create_producer_minimal(self) -> None:
        """Test creating a producer with minimal fields."""
        producer = Producer(canonical_name="Domaine de la Romanée-Conti")

        assert producer.canonical_name == "Domaine de la Romanée-Conti"
        assert producer.aliases == []
        assert producer.country == ""
        assert producer.region == ""
        assert producer.website == ""
        assert producer.wikidata_id is None
        assert producer.id is not None

    def test_create_producer_full(self) -> None:
        """Test creating a producer with all fields."""
        producer = Producer(
            canonical_name="Ridge Vineyards",
            aliases=["Ridge", "Ridge Winery"],
            country="USA",
            region="California",
            website="https://ridgewine.com",
            wikidata_id="Q7332478",
        )

        assert producer.canonical_name == "Ridge Vineyards"
        assert producer.aliases == ["Ridge", "Ridge Winery"]
        assert producer.country == "USA"
        assert producer.wikidata_id == "Q7332478"

    def test_producer_name_validation(self) -> None:
        """Test that producer name cannot be empty."""
        with pytest.raises(ValueError, match="canonical_name cannot be empty"):
            Producer(canonical_name="")

        with pytest.raises(ValueError, match="canonical_name cannot be empty"):
            Producer(canonical_name="   ")

    def test_producer_name_stripped(self) -> None:
        """Test that producer name is stripped of whitespace."""
        producer = Producer(canonical_name="  Ridge Vineyards  ")
        assert producer.canonical_name == "Ridge Vineyards"


class TestWineModel:
    """Tests for Wine Pydantic model."""

    def test_create_wine_minimal(self) -> None:
        """Test creating a wine with minimal fields."""
        producer_id = uuid4()
        wine = Wine(producer_id=producer_id, canonical_name="Monte Bello")

        assert wine.producer_id == producer_id
        assert wine.canonical_name == "Monte Bello"
        assert wine.color is None
        assert wine.style is None
        assert wine.grapes == []

    def test_create_wine_full(self) -> None:
        """Test creating a wine with all fields."""
        producer_id = uuid4()
        region_id = uuid4()
        wine = Wine(
            producer_id=producer_id,
            canonical_name="Richebourg Grand Cru",
            aliases=["Richebourg"],
            color=WineColor.RED,
            style=WineStyle.STILL,
            grapes=["Pinot Noir"],
            appellation="Richebourg AOC",
            region_id=region_id,
        )

        assert wine.canonical_name == "Richebourg Grand Cru"
        assert wine.color == WineColor.RED
        assert wine.style == WineStyle.STILL
        assert wine.grapes == ["Pinot Noir"]
        assert wine.region_id == region_id

    def test_wine_name_validation(self) -> None:
        """Test that wine name cannot be empty."""
        with pytest.raises(ValueError, match="canonical_name cannot be empty"):
            Wine(producer_id=uuid4(), canonical_name="")


class TestVintageModel:
    """Tests for Vintage Pydantic model."""

    def test_create_vintage_minimal(self) -> None:
        """Test creating a vintage with minimal fields."""
        wine_id = uuid4()
        vintage = Vintage(wine_id=wine_id, year=2019)

        assert vintage.wine_id == wine_id
        assert vintage.year == 2019
        assert vintage.bottle_size_ml == 750
        assert vintage.abv is None
        assert vintage.tech_sheet_attrs == {}

    def test_create_vintage_full(self) -> None:
        """Test creating a vintage with all fields."""
        wine_id = uuid4()
        vintage = Vintage(
            wine_id=wine_id,
            year=2018,
            bottle_size_ml=1500,
            abv=13.5,
            tech_sheet_attrs={"pH": 3.4, "TA": 5.8},
        )

        assert vintage.year == 2018
        assert vintage.bottle_size_ml == 1500
        assert vintage.abv == 13.5
        assert vintage.tech_sheet_attrs["pH"] == 3.4

    def test_vintage_year_validation(self) -> None:
        """Test that vintage year must be valid."""
        wine_id = uuid4()

        with pytest.raises(ValueError, match="year must be between 1800 and 2100"):
            Vintage(wine_id=wine_id, year=1700)

        with pytest.raises(ValueError, match="year must be between 1800 and 2100"):
            Vintage(wine_id=wine_id, year=2200)


class TestRegionModel:
    """Tests for Region Pydantic model."""

    def test_create_region_minimal(self) -> None:
        """Test creating a region with minimal fields."""
        region = Region(name="Burgundy")

        assert region.name == "Burgundy"
        assert region.parent_id is None
        assert region.country == ""
        assert region.hierarchy_level == RegionHierarchyLevel.REGION

    def test_create_region_full(self) -> None:
        """Test creating a region with all fields."""
        parent_id = uuid4()
        region = Region(
            name="Côte de Nuits",
            parent_id=parent_id,
            aliases=["Cote de Nuits"],
            country="France",
            wikidata_id="Q1141888",
            hierarchy_level=RegionHierarchyLevel.SUBREGION,
        )

        assert region.name == "Côte de Nuits"
        assert region.parent_id == parent_id
        assert region.hierarchy_level == RegionHierarchyLevel.SUBREGION

    def test_region_name_validation(self) -> None:
        """Test that region name cannot be empty."""
        with pytest.raises(ValueError, match="name cannot be empty"):
            Region(name="")


class TestGrapeVarietyModel:
    """Tests for GrapeVariety Pydantic model."""

    def test_create_grape_minimal(self) -> None:
        """Test creating a grape variety with minimal fields."""
        grape = GrapeVariety(canonical_name="Pinot Noir")

        assert grape.canonical_name == "Pinot Noir"
        assert grape.aliases == []
        assert grape.wikidata_id is None

    def test_create_grape_full(self) -> None:
        """Test creating a grape variety with all fields."""
        grape = GrapeVariety(
            canonical_name="Cabernet Sauvignon",
            aliases=["Cabernet", "Cab Sauv"],
            wikidata_id="Q11936",
        )

        assert grape.canonical_name == "Cabernet Sauvignon"
        assert grape.aliases == ["Cabernet", "Cab Sauv"]

    def test_grape_name_validation(self) -> None:
        """Test that grape name cannot be empty."""
        with pytest.raises(ValueError, match="canonical_name cannot be empty"):
            GrapeVariety(canonical_name="")


class TestSourceModel:
    """Tests for Source Pydantic model."""

    def test_create_source_minimal(self) -> None:
        """Test creating a source with minimal fields."""
        source = Source(domain="wine-searcher.com", adapter_type="json_ld")

        assert source.domain == "wine-searcher.com"
        assert source.adapter_type == "json_ld"
        assert source.enabled is True
        assert source.rate_limit_config["requests_per_second"] == 1.0

    def test_source_domain_normalized(self) -> None:
        """Test that domain is normalized to lowercase."""
        source = Source(domain="Wine-Searcher.COM", adapter_type="html")
        assert source.domain == "wine-searcher.com"

    def test_source_domain_validation(self) -> None:
        """Test that domain cannot be empty."""
        with pytest.raises(ValueError, match="domain cannot be empty"):
            Source(domain="", adapter_type="test")


class TestSnapshotModel:
    """Tests for Snapshot Pydantic model."""

    def test_create_snapshot(self) -> None:
        """Test creating a snapshot."""
        source_id = uuid4()
        snapshot = Snapshot(
            source_id=source_id,
            url="https://example.com/wine/123",
            content_hash="abc123def456",
        )

        assert snapshot.source_id == source_id
        assert snapshot.url == "https://example.com/wine/123"
        assert snapshot.content_hash == "abc123def456"
        assert snapshot.status == SnapshotStatus.PENDING
        assert snapshot.mime_type == "text/html"

    def test_snapshot_url_validation(self) -> None:
        """Test that URL cannot be empty."""
        with pytest.raises(ValueError, match="url cannot be empty"):
            Snapshot(source_id=uuid4(), url="", content_hash="hash")


class TestListingModel:
    """Tests for Listing Pydantic model."""

    def test_create_listing_minimal(self) -> None:
        """Test creating a listing with minimal fields."""
        source_id = uuid4()
        snapshot_id = uuid4()
        listing = Listing(
            source_id=source_id,
            snapshot_id=snapshot_id,
            url="https://example.com/wine/123",
        )

        assert listing.source_id == source_id
        assert listing.snapshot_id == snapshot_id
        assert listing.title == ""
        assert listing.upc is None
        assert listing.price is None

    def test_create_listing_full(self) -> None:
        """Test creating a listing with all fields."""
        listing = Listing(
            source_id=uuid4(),
            snapshot_id=uuid4(),
            url="https://example.com/wine/123",
            title="Ridge Monte Bello 2018",
            sku="RMB2018",
            upc="012345678901",
            ean="1234567890123",
            price=199.99,
            currency="USD",
            parsed_fields={"producer": "Ridge", "vintage": 2018},
        )

        assert listing.title == "Ridge Monte Bello 2018"
        assert listing.upc == "012345678901"
        assert listing.price == 199.99


class TestListingMatchModel:
    """Tests for ListingMatch Pydantic model."""

    def test_create_listing_match(self) -> None:
        """Test creating a listing match."""
        listing_id = uuid4()
        entity_id = uuid4()
        match = ListingMatch(
            listing_id=listing_id,
            entity_type=EntityType.VINTAGE,
            entity_id=entity_id,
            confidence=0.95,
        )

        assert match.listing_id == listing_id
        assert match.entity_type == EntityType.VINTAGE
        assert match.confidence == 0.95
        assert match.decision == MatchDecision.AUTO

    def test_confidence_validation(self) -> None:
        """Test that confidence must be between 0 and 1."""
        with pytest.raises(ValueError):
            ListingMatch(
                listing_id=uuid4(),
                entity_type=EntityType.WINE,
                entity_id=uuid4(),
                confidence=1.5,
            )


class TestFieldProvenanceModel:
    """Tests for FieldProvenance Pydantic model."""

    def test_create_field_provenance(self) -> None:
        """Test creating a field provenance record."""
        source_id = uuid4()
        entity_id = uuid4()
        provenance = FieldProvenance(
            entity_type=EntityType.WINE,
            entity_id=entity_id,
            field_path="grapes[0]",
            value="Pinot Noir",
            source_id=source_id,
            source_url="https://example.com/wine/123",
            fetched_at=datetime.now(UTC),
            extractor_version="1.0.0",
            confidence=0.9,
        )

        assert provenance.entity_type == EntityType.WINE
        assert provenance.field_path == "grapes[0]"
        assert provenance.value == "Pinot Noir"
        assert provenance.confidence == 0.9

    def test_field_path_validation(self) -> None:
        """Test that field_path cannot be empty."""
        with pytest.raises(ValueError, match="field_path cannot be empty"):
            FieldProvenance(
                entity_type=EntityType.WINE,
                entity_id=uuid4(),
                field_path="",
                value="test",
                source_id=uuid4(),
                source_url="https://example.com",
                fetched_at=datetime.now(UTC),
                extractor_version="1.0",
                confidence=0.9,
            )


class TestCatalogSearchRequest:
    """Tests for CatalogSearchRequest model."""

    def test_default_values(self) -> None:
        """Test default values for search request."""
        request = CatalogSearchRequest()

        assert request.query == ""
        assert request.producer is None
        assert request.vintage_year is None
        assert request.page == 1
        assert request.page_size == 20

    def test_with_filters(self) -> None:
        """Test search request with filters."""
        request = CatalogSearchRequest(
            query="Burgundy",
            country="France",
            vintage_year=2019,
            page=2,
            page_size=10,
        )

        assert request.query == "Burgundy"
        assert request.country == "France"
        assert request.vintage_year == 2019
        assert request.page == 2


class TestCatalogStats:
    """Tests for CatalogStats model."""

    def test_default_values(self) -> None:
        """Test default values for catalog stats."""
        stats = CatalogStats()

        assert stats.total_producers == 0
        assert stats.total_wines == 0
        assert stats.total_vintages == 0
        assert stats.total_regions == 0
        assert stats.total_grapes == 0
        assert stats.total_sources == 0
        assert stats.total_listings == 0

    def test_with_values(self) -> None:
        """Test catalog stats with values."""
        stats = CatalogStats(
            total_producers=100,
            total_wines=500,
            total_vintages=2000,
        )

        assert stats.total_producers == 100
        assert stats.total_wines == 500
        assert stats.total_vintages == 2000
