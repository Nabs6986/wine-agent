"""Tests for catalog API routes."""

import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from wine_agent.db.models import Base


@pytest.fixture
def temp_db_path():
    """Create a temporary database file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir) / "test_catalog_routes.db"


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
def session_factory(engine):
    """Create a session factory for testing."""
    return sessionmaker(bind=engine)


@pytest.fixture
def mock_meilisearch():
    """Create a mock Meilisearch service."""
    mock = MagicMock()
    mock.is_available.return_value = False
    mock.index_producer.return_value = None
    mock.index_wine_without_vintage.return_value = None
    mock.index_wine_vintage.return_value = None
    mock.index_region.return_value = None
    mock.search_wines.return_value = ([], 0)
    mock.get_stats.return_value = {"available": False}
    return mock


@pytest.fixture
def test_client(session_factory, mock_meilisearch, monkeypatch):
    """Create a test client with mocked dependencies."""
    # Remove wine_agent.web modules to force reimport with mocks
    modules_to_remove = [key for key in sys.modules if key.startswith("wine_agent.web")]
    for mod in modules_to_remove:
        del sys.modules[mod]

    # Mock run_migrations before importing the app module
    import wine_agent.db.engine
    monkeypatch.setattr(wine_agent.db.engine, "run_migrations", lambda: None)

    from wine_agent.web.app import create_app
    from wine_agent.services.catalog_service import CatalogService

    app = create_app()

    # Override the session context manager
    def override_get_session():
        session = session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    # Patch get_session
    with patch("wine_agent.web.routes.catalog.get_session") as mock_get_session:
        mock_get_session.return_value.__enter__ = lambda s: session_factory()
        mock_get_session.return_value.__exit__ = lambda s, *args: None

        # Create a session for patching get_catalog_service
        with patch("wine_agent.web.routes.catalog.get_catalog_service") as mock_get_catalog:
            def create_mock_service(session):
                return CatalogService(session=session, meilisearch=mock_meilisearch)

            mock_get_catalog.side_effect = create_mock_service

            client = TestClient(app)
            yield client


@pytest.fixture
def client_with_db(session_factory, mock_meilisearch, monkeypatch):
    """Create a test client with actual database access."""
    # Remove wine_agent.web modules to force reimport with mocks
    modules_to_remove = [key for key in sys.modules if key.startswith("wine_agent.web")]
    for mod in modules_to_remove:
        del sys.modules[mod]

    # Mock run_migrations before importing the app module
    import wine_agent.db.engine
    monkeypatch.setattr(wine_agent.db.engine, "run_migrations", lambda: None)

    from wine_agent.web.app import create_app
    from wine_agent.services.catalog_service import CatalogService

    app = create_app()
    session = session_factory()

    def mock_get_session_cm():
        class SessionCM:
            def __enter__(self):
                return session

            def __exit__(self, *args):
                pass
        return SessionCM()

    def mock_get_catalog_service(sess):
        return CatalogService(session=sess, meilisearch=mock_meilisearch)

    with patch("wine_agent.web.routes.catalog.get_session", mock_get_session_cm):
        with patch("wine_agent.web.routes.catalog.get_catalog_service", mock_get_catalog_service):
            client = TestClient(app)
            yield client, session

    session.close()


class TestParseInt:
    """Tests for _parse_int helper function."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, monkeypatch):
        """Prevent database operations when importing the catalog module."""
        # Remove wine_agent.web modules to force reimport with mocks
        modules_to_remove = [key for key in sys.modules if key.startswith("wine_agent.web")]
        for mod in modules_to_remove:
            del sys.modules[mod]

        # Mock run_migrations before importing
        import wine_agent.db.engine
        monkeypatch.setattr(wine_agent.db.engine, "run_migrations", lambda: None)

    def test_parse_valid_int(self):
        """Test parsing a valid integer string."""
        from wine_agent.web.routes.catalog import _parse_int
        assert _parse_int("2019") == 2019

    def test_parse_none(self):
        """Test parsing None returns None."""
        from wine_agent.web.routes.catalog import _parse_int
        assert _parse_int(None) is None

    def test_parse_empty_string(self):
        """Test parsing empty string returns None."""
        from wine_agent.web.routes.catalog import _parse_int
        assert _parse_int("") is None

    def test_parse_invalid_string(self):
        """Test parsing invalid string returns None."""
        from wine_agent.web.routes.catalog import _parse_int
        assert _parse_int("abc") is None


class TestAPISearchCatalog:
    """Tests for API search endpoint."""

    def test_search_empty_catalog(self, client_with_db):
        """Test searching an empty catalog."""
        client, _ = client_with_db
        response = client.get("/catalog/api/search")

        assert response.status_code == 200
        data = response.json()
        assert data["results"] == []
        assert data["total_count"] == 0
        assert data["page"] == 1

    def test_search_with_query(self, client_with_db):
        """Test searching with a query string."""
        client, _ = client_with_db
        response = client.get("/catalog/api/search?q=test")

        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert "total_count" in data

    def test_search_with_filters(self, client_with_db):
        """Test searching with various filters."""
        client, _ = client_with_db
        response = client.get(
            "/catalog/api/search?country=France&region=Burgundy&vintage=2019"
        )

        assert response.status_code == 200
        data = response.json()
        assert "results" in data

    def test_search_pagination(self, client_with_db):
        """Test search pagination parameters."""
        client, _ = client_with_db
        response = client.get("/catalog/api/search?page=2&page_size=10")

        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 2
        assert data["page_size"] == 10


class TestAPIProducerEndpoints:
    """Tests for producer API endpoints."""

    def test_create_producer(self, client_with_db):
        """Test creating a producer via API."""
        client, _ = client_with_db
        response = client.post(
            "/catalog/api/producers",
            data={
                "canonical_name": "Ridge Vineyards",
                "country": "USA",
                "region": "California",
                "website": "https://ridgewine.com",
                "aliases": "Ridge, Ridge Winery",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert "producer" in data
        assert data["producer"]["canonical_name"] == "Ridge Vineyards"
        assert data["producer"]["country"] == "USA"
        assert "Ridge" in data["producer"]["aliases"]

    def test_get_producer(self, client_with_db):
        """Test getting a producer by ID."""
        client, session = client_with_db

        # First create a producer
        from wine_agent.services.catalog_service import CatalogService
        from unittest.mock import MagicMock

        mock_meili = MagicMock()
        mock_meili.is_available.return_value = False
        mock_meili.index_producer.return_value = None

        service = CatalogService(session=session, meilisearch=mock_meili)
        producer = service.create_producer(canonical_name="Test Producer")
        session.commit()

        # Then get it
        response = client.get(f"/catalog/api/producers/{producer.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["producer"]["canonical_name"] == "Test Producer"
        assert "wines" in data

    def test_get_producer_not_found(self, client_with_db):
        """Test getting a non-existent producer."""
        client, _ = client_with_db
        response = client.get("/catalog/api/producers/00000000-0000-0000-0000-000000000000")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


class TestAPIWineEndpoints:
    """Tests for wine API endpoints."""

    def test_create_wine(self, client_with_db):
        """Test creating a wine via API."""
        client, session = client_with_db

        # First create a producer
        from wine_agent.services.catalog_service import CatalogService
        from unittest.mock import MagicMock

        mock_meili = MagicMock()
        mock_meili.is_available.return_value = False
        mock_meili.index_producer.return_value = None
        mock_meili.index_wine_without_vintage.return_value = None

        service = CatalogService(session=session, meilisearch=mock_meili)
        producer = service.create_producer(canonical_name="Test Producer")
        session.commit()

        # Then create a wine
        response = client.post(
            "/catalog/api/wines",
            data={
                "producer_id": str(producer.id),
                "canonical_name": "Monte Bello",
                "color": "red",
                "style": "still",
                "appellation": "Santa Cruz Mountains",
                "grapes": "Cabernet Sauvignon, Merlot",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["wine"]["canonical_name"] == "Monte Bello"
        assert data["wine"]["color"] == "red"

    def test_get_wine(self, client_with_db):
        """Test getting a wine by ID."""
        client, session = client_with_db

        # Create producer and wine
        from wine_agent.services.catalog_service import CatalogService
        from unittest.mock import MagicMock

        mock_meili = MagicMock()
        mock_meili.is_available.return_value = False
        mock_meili.index_producer.return_value = None
        mock_meili.index_wine_without_vintage.return_value = None

        service = CatalogService(session=session, meilisearch=mock_meili)
        producer = service.create_producer(canonical_name="Test Producer")
        wine = service.create_wine(producer_id=producer.id, canonical_name="Test Wine")
        session.commit()

        response = client.get(f"/catalog/api/wines/{wine.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["wine"]["canonical_name"] == "Test Wine"
        assert "producer" in data
        assert "vintages" in data

    def test_get_wine_not_found(self, client_with_db):
        """Test getting a non-existent wine."""
        client, _ = client_with_db
        response = client.get("/catalog/api/wines/00000000-0000-0000-0000-000000000000")

        assert response.status_code == 404


class TestAPIVintageEndpoints:
    """Tests for vintage API endpoints."""

    def test_create_vintage(self, client_with_db):
        """Test creating a vintage via API."""
        client, session = client_with_db

        # Create producer and wine
        from wine_agent.services.catalog_service import CatalogService
        from unittest.mock import MagicMock

        mock_meili = MagicMock()
        mock_meili.is_available.return_value = False
        mock_meili.index_producer.return_value = None
        mock_meili.index_wine_without_vintage.return_value = None
        mock_meili.index_wine_vintage.return_value = None

        service = CatalogService(session=session, meilisearch=mock_meili)
        producer = service.create_producer(canonical_name="Test Producer")
        wine = service.create_wine(producer_id=producer.id, canonical_name="Test Wine")
        session.commit()

        # Create vintage
        response = client.post(
            "/catalog/api/vintages",
            data={
                "wine_id": str(wine.id),
                "year": 2019,
                "bottle_size_ml": 750,
                "abv": 13.5,
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["vintage"]["year"] == 2019
        assert data["vintage"]["abv"] == 13.5

    def test_get_vintage(self, client_with_db):
        """Test getting a vintage by ID."""
        client, session = client_with_db

        # Create full hierarchy
        from wine_agent.services.catalog_service import CatalogService
        from unittest.mock import MagicMock

        mock_meili = MagicMock()
        mock_meili.is_available.return_value = False
        mock_meili.index_producer.return_value = None
        mock_meili.index_wine_without_vintage.return_value = None
        mock_meili.index_wine_vintage.return_value = None

        service = CatalogService(session=session, meilisearch=mock_meili)
        producer = service.create_producer(canonical_name="Test Producer")
        wine = service.create_wine(producer_id=producer.id, canonical_name="Test Wine")
        vintage = service.create_vintage(wine_id=wine.id, year=2020)
        session.commit()

        response = client.get(f"/catalog/api/vintages/{vintage.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["vintage"]["year"] == 2020
        assert data["wine"]["canonical_name"] == "Test Wine"
        assert data["producer"]["canonical_name"] == "Test Producer"

    def test_get_vintage_not_found(self, client_with_db):
        """Test getting a non-existent vintage."""
        client, _ = client_with_db
        response = client.get("/catalog/api/vintages/00000000-0000-0000-0000-000000000000")

        assert response.status_code == 404


class TestAPITastingLinking:
    """Tests for tasting linking endpoint."""

    def test_link_tasting_missing_ids(self, client_with_db):
        """Test linking without providing IDs raises error."""
        client, _ = client_with_db
        response = client.post(
            "/catalog/api/tastings/some-tasting-id/link",
            data={},
        )

        assert response.status_code == 400
        assert "vintage_id or wine_id" in response.json()["detail"]


class TestAPIStats:
    """Tests for stats endpoint."""

    def test_get_stats(self, client_with_db):
        """Test getting catalog statistics."""
        client, _ = client_with_db
        response = client.get("/catalog/api/stats")

        assert response.status_code == 200
        data = response.json()
        assert "catalog" in data
        assert "meilisearch" in data
        assert data["catalog"]["total_producers"] == 0


class TestHTMLRoutes:
    """Tests for HTML routes (basic smoke tests)."""

    def test_catalog_index(self, client_with_db):
        """Test catalog index page loads."""
        client, _ = client_with_db
        response = client.get("/catalog")

        # Should return 200 or redirect
        assert response.status_code in [200, 302, 303]

    def test_catalog_stats_page(self, client_with_db):
        """Test catalog stats page loads."""
        client, _ = client_with_db
        response = client.get("/catalog/stats")

        assert response.status_code in [200, 302, 303]

    def test_new_producer_form(self, client_with_db):
        """Test new producer form loads."""
        client, _ = client_with_db
        response = client.get("/catalog/producers/new")

        assert response.status_code in [200, 302, 303]

    def test_new_wine_form(self, client_with_db):
        """Test new wine form loads."""
        client, _ = client_with_db
        response = client.get("/catalog/wines/new")

        assert response.status_code in [200, 302, 303]

    def test_new_vintage_form(self, client_with_db):
        """Test new vintage form loads."""
        client, _ = client_with_db
        response = client.get("/catalog/vintages/new")

        assert response.status_code in [200, 302, 303]


class TestFullAPIWorkflow:
    """Integration tests for full API workflow."""

    def test_create_full_wine_entry(self, client_with_db):
        """Test creating a complete wine entry through the API."""
        client, _ = client_with_db

        # Create producer
        producer_response = client.post(
            "/catalog/api/producers",
            data={
                "canonical_name": "Domaine de la Romanée-Conti",
                "country": "France",
                "region": "Burgundy",
            },
        )
        assert producer_response.status_code == 201
        producer_id = producer_response.json()["producer"]["id"]

        # Create wine
        wine_response = client.post(
            "/catalog/api/wines",
            data={
                "producer_id": producer_id,
                "canonical_name": "La Tâche Grand Cru",
                "color": "red",
                "style": "still",
                "grapes": "Pinot Noir",
                "appellation": "La Tâche AOC",
            },
        )
        assert wine_response.status_code == 201
        wine_id = wine_response.json()["wine"]["id"]

        # Create vintage
        vintage_response = client.post(
            "/catalog/api/vintages",
            data={
                "wine_id": wine_id,
                "year": 2018,
                "abv": 13.0,
            },
        )
        assert vintage_response.status_code == 201

        # Verify via stats
        stats_response = client.get("/catalog/api/stats")
        assert stats_response.status_code == 200
        stats = stats_response.json()["catalog"]
        assert stats["total_producers"] == 1
        assert stats["total_wines"] == 1
        assert stats["total_vintages"] == 1
