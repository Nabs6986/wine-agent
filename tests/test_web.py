"""Tests for web routes."""

import tempfile
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from wine_agent.core.enums import NoteSource, NoteStatus
from wine_agent.core.schema import InboxItem, TastingNote
from wine_agent.db.models import Base
from wine_agent.db.repositories import InboxRepository, TastingNoteRepository


@pytest.fixture
def temp_db_path():
    """Create a temporary database file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir) / "test.db"


@pytest.fixture
def test_engine(temp_db_path):
    """Create a test database engine."""
    url = f"sqlite:///{temp_db_path}"
    engine = create_engine(url, echo=False)
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def test_session(test_engine):
    """Create a database session for testing."""
    SessionLocal = sessionmaker(bind=test_engine)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def client(test_engine, monkeypatch):
    """Create a test client with mocked database."""
    from sqlalchemy.orm import sessionmaker

    # Create session factory for the test engine
    TestSessionLocal = sessionmaker(bind=test_engine)

    # Mock the get_session context manager
    from contextlib import contextmanager

    @contextmanager
    def mock_get_session():
        session = TestSessionLocal()
        try:
            yield session
        finally:
            session.close()

    # Apply the monkeypatch
    monkeypatch.setattr("wine_agent.web.routes.inbox.get_session", mock_get_session)
    monkeypatch.setattr("wine_agent.web.routes.notes.get_session", mock_get_session)

    # Also mock the init_db in app creation to prevent it from creating another DB
    monkeypatch.setattr("wine_agent.web.app.init_db", lambda: None)

    # Import and create app after mocking
    from wine_agent.web.app import create_app

    app = create_app()
    return TestClient(app)


class TestRootRoute:
    """Tests for root route."""

    def test_root_redirects_to_inbox(self, client: TestClient) -> None:
        """Test that root redirects to inbox."""
        response = client.get("/", follow_redirects=False)
        assert response.status_code == 302
        assert response.headers["location"] == "/inbox"


class TestInboxRoutes:
    """Tests for inbox routes."""

    def test_inbox_list_empty(self, client: TestClient) -> None:
        """Test inbox list when empty."""
        response = client.get("/inbox")
        assert response.status_code == 200
        assert "No inbox items found" in response.text

    def test_inbox_new_form(self, client: TestClient) -> None:
        """Test inbox new form renders."""
        response = client.get("/inbox/new")
        assert response.status_code == 200
        assert "New Tasting Note" in response.text
        assert "raw_text" in response.text

    def test_inbox_create(self, client: TestClient) -> None:
        """Test creating an inbox item."""
        response = client.post(
            "/inbox",
            data={
                "raw_text": "Great wine from Burgundy",
                "tags": "burgundy, pinot",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert "/inbox/" in response.headers["location"]

    def test_inbox_create_and_view(self, client: TestClient) -> None:
        """Test creating and viewing an inbox item."""
        # Create
        create_response = client.post(
            "/inbox",
            data={
                "raw_text": "2020 Chateau Margaux, amazing wine",
                "tags": "bordeaux",
            },
            follow_redirects=True,
        )
        assert create_response.status_code == 200
        assert "2020 Chateau Margaux" in create_response.text

    def test_inbox_list_with_items(self, client: TestClient) -> None:
        """Test inbox list with items."""
        # Create some items
        client.post("/inbox", data={"raw_text": "Wine 1", "tags": ""})
        client.post("/inbox", data={"raw_text": "Wine 2", "tags": ""})

        response = client.get("/inbox")
        assert response.status_code == 200
        assert "Wine 1" in response.text
        assert "Wine 2" in response.text

    def test_inbox_filter_open(self, client: TestClient) -> None:
        """Test inbox filter for open items."""
        response = client.get("/inbox?filter=open")
        assert response.status_code == 200
        assert 'class="filter-btn active"' in response.text

    def test_inbox_detail_not_found(self, client: TestClient) -> None:
        """Test inbox detail for nonexistent item."""
        fake_id = str(uuid4())
        response = client.get(f"/inbox/{fake_id}")
        assert response.status_code == 404

    def test_inbox_archive(self, client: TestClient) -> None:
        """Test archiving an inbox item."""
        # Create item
        create_response = client.post(
            "/inbox",
            data={"raw_text": "Wine to archive", "tags": ""},
            follow_redirects=False,
        )
        item_url = create_response.headers["location"]
        item_id = item_url.split("/")[-1]

        # Archive it
        archive_response = client.post(
            f"/inbox/{item_id}/archive",
            follow_redirects=False,
        )
        assert archive_response.status_code == 303

        # Verify it's archived (shows as converted)
        detail_response = client.get(f"/inbox/{item_id}")
        assert "Converted" in detail_response.text

    def test_inbox_convert_creates_draft(self, client: TestClient) -> None:
        """Test converting inbox item creates draft note."""
        # Create item
        create_response = client.post(
            "/inbox",
            data={"raw_text": "Wine to convert", "tags": ""},
            follow_redirects=False,
        )
        item_url = create_response.headers["location"]
        item_id = item_url.split("/")[-1]

        # Convert it
        convert_response = client.post(
            f"/inbox/{item_id}/convert",
            follow_redirects=False,
        )
        assert convert_response.status_code == 303
        assert "/notes/draft/" in convert_response.headers["location"]

    def test_inbox_convert_follow_to_draft(self, client: TestClient) -> None:
        """Test converting and following to draft note view."""
        # Create item
        create_response = client.post(
            "/inbox",
            data={"raw_text": "Amazing Barolo 2016", "tags": ""},
            follow_redirects=False,
        )
        item_url = create_response.headers["location"]
        item_id = item_url.split("/")[-1]

        # Convert and follow
        convert_response = client.post(
            f"/inbox/{item_id}/convert",
            follow_redirects=True,
        )
        assert convert_response.status_code == 200
        assert "Draft Tasting Note" in convert_response.text
        assert "Amazing Barolo 2016" in convert_response.text


class TestNotesRoutes:
    """Tests for notes routes."""

    def test_draft_not_found(self, client: TestClient) -> None:
        """Test draft detail for nonexistent note."""
        fake_id = str(uuid4())
        response = client.get(f"/notes/draft/{fake_id}")
        assert response.status_code == 404

    def test_draft_view_after_convert(self, client: TestClient) -> None:
        """Test draft view shows source info after convert."""
        # Create and convert item
        create_response = client.post(
            "/inbox",
            data={"raw_text": "Test wine for draft view", "tags": ""},
            follow_redirects=False,
        )
        item_id = create_response.headers["location"].split("/")[-1]

        # Convert
        convert_response = client.post(
            f"/inbox/{item_id}/convert",
            follow_redirects=True,
        )

        # Check draft view
        assert "Draft Tasting Note" in convert_response.text
        assert "Source" in convert_response.text
        assert "Test wine for draft view" in convert_response.text


class TestFullWorkflow:
    """Integration tests for full workflow."""

    def test_inbox_to_draft_workflow(self, client: TestClient) -> None:
        """Test complete workflow: create inbox -> convert -> view draft."""
        # Step 1: View empty inbox
        inbox_response = client.get("/inbox")
        assert inbox_response.status_code == 200
        assert "No inbox items found" in inbox_response.text

        # Step 2: Create new inbox item
        create_response = client.post(
            "/inbox",
            data={
                "raw_text": "2018 Ridge Monte Bello. Deep ruby color. Nose of cassis, graphite, and herbs.",
                "tags": "california, cabernet",
            },
            follow_redirects=True,
        )
        assert create_response.status_code == 200
        assert "2018 Ridge Monte Bello" in create_response.text

        # Step 3: View inbox list (now has item)
        inbox_response = client.get("/inbox")
        assert "2018 Ridge Monte Bello" in inbox_response.text
        assert "Open" in inbox_response.text

        # Step 4: Get item ID from the list page link
        # We need to find the item ID from somewhere - let's use the detail page
        # The item should be listed, so we search for the ID in the href

        # Step 5: Convert to draft
        # First, get the item ID by creating another and tracking it
        create_response2 = client.post(
            "/inbox",
            data={"raw_text": "Another test wine", "tags": ""},
            follow_redirects=False,
        )
        item_id = create_response2.headers["location"].split("/")[-1]

        convert_response = client.post(
            f"/inbox/{item_id}/convert",
            follow_redirects=True,
        )
        assert convert_response.status_code == 200
        assert "Draft Tasting Note" in convert_response.text

        # Step 6: Verify inbox shows as converted
        detail_response = client.get(f"/inbox/{item_id}")
        assert "Converted" in detail_response.text
        assert "View Draft Note" in detail_response.text

    def test_already_converted_redirects(self, client: TestClient) -> None:
        """Test that converting already converted item redirects to existing note."""
        # Create and convert
        create_response = client.post(
            "/inbox",
            data={"raw_text": "Wine to double convert", "tags": ""},
            follow_redirects=False,
        )
        item_id = create_response.headers["location"].split("/")[-1]

        # First convert
        first_convert = client.post(
            f"/inbox/{item_id}/convert",
            follow_redirects=False,
        )
        first_note_url = first_convert.headers["location"]

        # Second convert should redirect to same note
        second_convert = client.post(
            f"/inbox/{item_id}/convert",
            follow_redirects=False,
        )
        second_note_url = second_convert.headers["location"]

        assert first_note_url == second_note_url
