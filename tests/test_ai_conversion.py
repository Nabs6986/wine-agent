"""Tests for AI conversion pipeline."""

import json
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from wine_agent.core.enums import NoteSource, NoteStatus, QualityBand, WineColor
from wine_agent.core.schema import InboxItem, TastingNote
from wine_agent.db.models import Base
from wine_agent.db.repositories import (
    AIConversionRepository,
    InboxRepository,
    TastingNoteRepository,
)
from wine_agent.services.ai.client import AIProvider, GenerationResult
from wine_agent.services.ai.prompts import (
    PROMPT_VERSION,
    build_conversion_prompt,
    build_repair_prompt,
)


# Sample valid AI response matching TastingNote schema
SAMPLE_VALID_RESPONSE = {
    "wine": {
        "producer": "Ridge Vineyards",
        "cuvee": "Monte Bello",
        "vintage": 2018,
        "country": "USA",
        "region": "California",
        "subregion": "Santa Cruz Mountains",
        "grapes": ["Cabernet Sauvignon", "Merlot", "Petit Verdot"],
        "color": "red",
        "style": "still",
        "sweetness": "dry",
        "alcohol_percent": 13.5,
    },
    "context": {
        "tasting_date": "2024-01-15",
        "location": "Home",
        "food_pairing": "Grilled lamb",
    },
    "scores": {
        "subscores": {
            "appearance": 2,
            "nose": 11,
            "palate": 18,
            "structure_balance": 17,
            "finish": 9,
            "typicity_complexity": 14,
            "overall_judgment": 17,
        },
        "personal_enjoyment": 9,
        "value_for_money": 7,
    },
    "structure_levels": {
        "acidity": "medium",
        "tannin": "med_plus",
        "body": "full",
        "alcohol": "medium",
        "oak": "integrated",
    },
    "descriptors": {
        "primary_fruit": ["blackcurrant", "black cherry", "plum"],
        "secondary": ["cedar", "vanilla", "toast"],
        "tertiary": ["tobacco", "leather"],
        "non_fruit": ["graphite", "mineral"],
        "texture": ["firm", "structured"],
    },
    "confidence": {
        "level": "high",
        "uncertainty_notes": "",
    },
    "readiness": {
        "drink_or_hold": "hold",
        "window_start_year": 2025,
        "window_end_year": 2040,
        "notes": "Still quite young, will improve with age",
    },
    "nose_notes": "Intense aromas of blackcurrant and cedar with hints of graphite",
    "palate_notes": "Full-bodied with firm tannins, excellent structure",
    "conclusion": "A benchmark California Cabernet that will age gracefully",
}


@pytest.fixture
def temp_db_path():
    """Create a temporary database file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir) / "test.db"


@pytest.fixture
def engine(temp_db_path):
    """Create a test database engine."""
    url = f"sqlite:///{temp_db_path}"
    engine = create_engine(url, echo=False)
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


class TestPrompts:
    """Tests for prompt building."""

    def test_build_conversion_prompt_basic(self) -> None:
        """Test basic conversion prompt."""
        raw_text = "Amazing 2018 Ridge Monte Bello"
        prompt = build_conversion_prompt(raw_text)

        assert "Amazing 2018 Ridge Monte Bello" in prompt
        assert "RAW TASTING NOTES:" in prompt
        assert "JSON" in prompt

    def test_build_conversion_prompt_with_hints(self) -> None:
        """Test conversion prompt with hints."""
        raw_text = "Great wine"
        hints = {"producer": "Ridge", "vintage": 2018}
        prompt = build_conversion_prompt(raw_text, hints)

        assert "Great wine" in prompt
        assert "ADDITIONAL HINTS" in prompt
        assert "producer: Ridge" in prompt
        assert "vintage: 2018" in prompt

    def test_build_repair_prompt(self) -> None:
        """Test repair prompt building."""
        invalid_json = '{"wine": {"producer": "Test"'
        error = "Expecting ',' delimiter"
        prompt = build_repair_prompt(invalid_json, error)

        assert invalid_json in prompt
        assert error in prompt
        assert "fix" in prompt.lower() or "repair" in prompt.lower()


class TestGenerationResult:
    """Tests for GenerationResult model."""

    def test_successful_result(self) -> None:
        """Test successful generation result."""
        note = TastingNote()
        result = GenerationResult(
            success=True,
            raw_response=json.dumps(SAMPLE_VALID_RESPONSE),
            parsed_json=SAMPLE_VALID_RESPONSE,
            tasting_note=note,
        )
        assert result.success is True
        assert result.tasting_note is not None
        assert result.error_message is None

    def test_failed_result(self) -> None:
        """Test failed generation result."""
        result = GenerationResult(
            success=False,
            raw_response="invalid json",
            error_message="JSON parse error",
            repair_attempts=2,
        )
        assert result.success is False
        assert result.error_message == "JSON parse error"
        assert result.repair_attempts == 2
        assert result.tasting_note is None


try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False


class TestMockedAIClient:
    """Tests with mocked AI client."""

    @pytest.mark.skipif(not HAS_ANTHROPIC, reason="anthropic package not installed")
    def test_parse_valid_json_response(self) -> None:
        """Test parsing a valid JSON response."""
        from wine_agent.services.ai.providers.anthropic import AnthropicClient

        # Create a mock client that doesn't need a real API key
        with patch("anthropic.Anthropic"):
            client = AnthropicClient(api_key="test-key")

        # Test the parsing logic directly
        raw_response = json.dumps(SAMPLE_VALID_RESPONSE)
        result = client._parse_and_validate(raw_response)

        assert result.success is True
        assert result.tasting_note is not None
        assert result.tasting_note.wine.producer == "Ridge Vineyards"
        assert result.tasting_note.wine.vintage == 2018
        assert result.tasting_note.scores.total == 88  # Sum of subscores

    @pytest.mark.skipif(not HAS_ANTHROPIC, reason="anthropic package not installed")
    def test_parse_json_with_markdown_blocks(self) -> None:
        """Test parsing JSON wrapped in markdown code blocks."""
        from wine_agent.services.ai.providers.anthropic import AnthropicClient

        with patch("anthropic.Anthropic"):
            client = AnthropicClient(api_key="test-key")

        # Wrap in markdown code blocks (common AI response format)
        raw_response = f"```json\n{json.dumps(SAMPLE_VALID_RESPONSE)}\n```"
        result = client._parse_and_validate(raw_response)

        assert result.success is True
        assert result.tasting_note is not None

    @pytest.mark.skipif(not HAS_ANTHROPIC, reason="anthropic package not installed")
    def test_parse_invalid_json_no_repair(self) -> None:
        """Test handling invalid JSON without repair."""
        from wine_agent.services.ai.providers.anthropic import AnthropicClient

        with patch("anthropic.Anthropic"):
            client = AnthropicClient(api_key="test-key")
            # Mock repair to return same invalid content
            client.repair_json = MagicMock(return_value='{"incomplete":')

        result = client._parse_and_validate('{"incomplete":')

        assert result.success is False
        assert "JSON parse error" in result.error_message
        assert result.repair_attempts == 2  # Max repair attempts

    @pytest.mark.skipif(not HAS_ANTHROPIC, reason="anthropic package not installed")
    def test_generate_structured_note_api_call(self) -> None:
        """Test the full generate flow with mocked API."""
        from wine_agent.services.ai.providers.anthropic import AnthropicClient

        mock_anthropic = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=json.dumps(SAMPLE_VALID_RESPONSE))]
        mock_anthropic.messages.create.return_value = mock_response

        with patch("anthropic.Anthropic", return_value=mock_anthropic):
            client = AnthropicClient(api_key="test-key")
            result = client.generate_structured_note(
                raw_text="2018 Ridge Monte Bello, amazing wine"
            )

        assert result.success is True
        assert result.tasting_note is not None
        assert result.tasting_note.wine.producer == "Ridge Vineyards"
        mock_anthropic.messages.create.assert_called_once()


class TestConversionService:
    """Tests for ConversionService."""

    def test_convert_inbox_item_success(self, session: Session) -> None:
        """Test successful conversion of inbox item."""
        from wine_agent.services.ai.client import AIClient, GenerationResult
        from wine_agent.services.ai.conversion import ConversionService

        # Create inbox item
        inbox_repo = InboxRepository(session)
        inbox_item = InboxItem(raw_text="2018 Ridge Monte Bello, fantastic wine")
        inbox_repo.create(inbox_item)
        session.commit()

        # Create mock AI client
        mock_client = MagicMock(spec=AIClient)
        mock_client.provider = AIProvider.ANTHROPIC
        mock_client.model = "claude-3-sonnet"

        tasting_note = TastingNote.model_validate(SAMPLE_VALID_RESPONSE)
        mock_client.generate_structured_note.return_value = GenerationResult(
            success=True,
            raw_response=json.dumps(SAMPLE_VALID_RESPONSE),
            parsed_json=SAMPLE_VALID_RESPONSE,
            tasting_note=tasting_note,
            repair_attempts=0,
        )

        # Run conversion
        service = ConversionService(session, ai_client=mock_client)
        result = service.convert_inbox_item(inbox_item.id)
        session.commit()

        assert result.success is True
        assert result.tasting_note is not None
        assert result.tasting_note.wine.producer == "Ridge Vineyards"
        assert result.tasting_note.source == NoteSource.INBOX_CONVERTED
        assert result.tasting_note.status == NoteStatus.DRAFT
        assert result.conversion_run is not None
        assert result.conversion_run.success is True

        # Verify inbox item marked as converted
        updated_item = inbox_repo.get_by_id(inbox_item.id)
        assert updated_item.converted is True

    def test_convert_inbox_item_failure(self, session: Session) -> None:
        """Test failed conversion of inbox item."""
        from wine_agent.services.ai.client import AIClient, GenerationResult
        from wine_agent.services.ai.conversion import ConversionService

        # Create inbox item
        inbox_repo = InboxRepository(session)
        inbox_item = InboxItem(raw_text="Bad input")
        inbox_repo.create(inbox_item)
        session.commit()

        # Create mock AI client that fails
        mock_client = MagicMock(spec=AIClient)
        mock_client.provider = AIProvider.ANTHROPIC
        mock_client.model = "claude-3-sonnet"
        mock_client.generate_structured_note.return_value = GenerationResult(
            success=False,
            raw_response="invalid response",
            error_message="Parse error",
            repair_attempts=2,
        )

        # Run conversion
        service = ConversionService(session, ai_client=mock_client)
        result = service.convert_inbox_item(inbox_item.id)
        session.commit()

        assert result.success is False
        assert result.error_message == "Parse error"
        assert result.tasting_note is None

        # Verify conversion run was saved
        conversion_repo = AIConversionRepository(session)
        runs = conversion_repo.get_by_inbox_item_id(inbox_item.id)
        assert len(runs) == 1
        assert runs[0].success is False

    def test_convert_nonexistent_item(self, session: Session) -> None:
        """Test converting a nonexistent inbox item."""
        from wine_agent.services.ai.conversion import ConversionService

        mock_client = MagicMock()
        service = ConversionService(session, ai_client=mock_client)

        result = service.convert_inbox_item(uuid4())

        assert result.success is False
        assert "not found" in result.error_message

    def test_convert_already_converted_item(self, session: Session) -> None:
        """Test converting an already converted inbox item."""
        from wine_agent.services.ai.conversion import ConversionService

        # Create inbox item and note
        inbox_repo = InboxRepository(session)
        note_repo = TastingNoteRepository(session)

        inbox_item = InboxItem(raw_text="Test", converted=True)
        inbox_repo.create(inbox_item)

        existing_note = TastingNote(
            inbox_item_id=inbox_item.id,
            source=NoteSource.INBOX_CONVERTED,
        )
        note_repo.create(existing_note)
        session.commit()

        # Try to convert again
        mock_client = MagicMock()
        service = ConversionService(session, ai_client=mock_client)
        result = service.convert_inbox_item(inbox_item.id)

        assert result.success is True
        assert result.tasting_note.id == existing_note.id
        # AI client should not be called
        mock_client.generate_structured_note.assert_not_called()

    def test_conversion_history(self, session: Session) -> None:
        """Test getting conversion history for an item."""
        from wine_agent.services.ai.client import AIClient, GenerationResult
        from wine_agent.services.ai.conversion import ConversionService

        # Create inbox item
        inbox_repo = InboxRepository(session)
        inbox_item = InboxItem(raw_text="Test wine")
        inbox_repo.create(inbox_item)
        session.commit()

        # Create mock client that fails first, succeeds second
        mock_client = MagicMock(spec=AIClient)
        mock_client.provider = AIProvider.ANTHROPIC
        mock_client.model = "claude-3-sonnet"

        # First call fails
        mock_client.generate_structured_note.return_value = GenerationResult(
            success=False,
            raw_response="error",
            error_message="First attempt failed",
            repair_attempts=2,
        )

        service = ConversionService(session, ai_client=mock_client)
        result1 = service.convert_inbox_item(inbox_item.id)
        session.commit()

        assert result1.success is False

        # Reset converted flag for retry
        inbox_item = inbox_repo.get_by_id(inbox_item.id)

        # Second call succeeds
        tasting_note = TastingNote.model_validate(SAMPLE_VALID_RESPONSE)
        mock_client.generate_structured_note.return_value = GenerationResult(
            success=True,
            raw_response=json.dumps(SAMPLE_VALID_RESPONSE),
            parsed_json=SAMPLE_VALID_RESPONSE,
            tasting_note=tasting_note,
            repair_attempts=0,
        )

        result2 = service.convert_inbox_item(inbox_item.id)
        session.commit()

        # Get conversion history
        history = service.get_conversion_history(inbox_item.id)
        assert len(history) == 2
        # History is ordered by created_at desc
        assert history[0].success is True
        assert history[1].success is False


class TestTastingNoteValidation:
    """Tests for TastingNote validation from AI responses."""

    def test_valid_response_creates_note(self) -> None:
        """Test that a valid response creates a proper TastingNote."""
        note = TastingNote.model_validate(SAMPLE_VALID_RESPONSE)

        assert note.wine.producer == "Ridge Vineyards"
        assert note.wine.vintage == 2018
        assert note.wine.color == WineColor.RED
        assert "Cabernet Sauvignon" in note.wine.grapes
        assert note.scores.total == 88
        assert note.scores.quality_band == QualityBand.GOOD

    def test_minimal_response_creates_note(self) -> None:
        """Test that a minimal response creates a valid TastingNote."""
        minimal = {
            "wine": {"producer": "Test Producer"},
            "scores": {
                "subscores": {
                    "appearance": 1,
                    "nose": 8,
                    "palate": 14,
                    "structure_balance": 14,
                    "finish": 7,
                    "typicity_complexity": 10,
                    "overall_judgment": 14,
                }
            },
        }
        note = TastingNote.model_validate(minimal)

        assert note.wine.producer == "Test Producer"
        assert note.wine.vintage is None
        assert note.scores.total == 68
        assert note.scores.quality_band == QualityBand.POOR

    def test_empty_response_creates_default_note(self) -> None:
        """Test that an empty response creates a note with defaults."""
        note = TastingNote.model_validate({})

        assert note.wine.producer == ""
        assert note.scores.total == 0
        assert note.scores.quality_band == QualityBand.POOR


class TestSanitizeAIResponse:
    """Tests for the sanitize_ai_response function."""

    def test_converts_null_strings_to_empty(self) -> None:
        """Test that null values for string fields become empty strings."""
        from wine_agent.services.ai.client import sanitize_ai_response

        data = {
            "wine": {
                "producer": None,
                "cuvee": "Test Wine",
                "region": None,
            },
            "context": {
                "location": None,
                "occasion": "Dinner",
            },
            "nose_notes": None,
            "palate_notes": "Fruity and complex",
        }

        result = sanitize_ai_response(data)

        # Null string fields should become empty strings
        assert result["wine"]["producer"] == ""
        assert result["wine"]["region"] == ""
        assert result["context"]["location"] == ""
        assert result["nose_notes"] == ""

        # Non-null values should be preserved
        assert result["wine"]["cuvee"] == "Test Wine"
        assert result["context"]["occasion"] == "Dinner"
        assert result["palate_notes"] == "Fruity and complex"

    def test_pydantic_validates_after_sanitization(self) -> None:
        """Test that sanitized data passes Pydantic validation."""
        from wine_agent.services.ai.client import sanitize_ai_response

        # This is similar to what the AI might return - nulls for unknown fields
        ai_response = {
            "wine": {
                "producer": None,
                "cuvee": None,
                "vintage": 2020,
                "country": "France",
                "region": "Burgundy",
                "subregion": None,
                "appellation": None,
                "vineyard": None,
                "grapes": ["Pinot Noir"],
                "color": "red",
            },
            "context": {
                "location": None,
                "glassware": None,
                "companions": None,
                "occasion": None,
                "food_pairing": None,
            },
            "nose_notes": "Cherry and earth",
            "palate_notes": None,
            "appearance_notes": None,
        }

        sanitized = sanitize_ai_response(ai_response)
        # This should not raise a validation error
        note = TastingNote.model_validate(sanitized)

        assert note.wine.producer == ""
        assert note.wine.vintage == 2020
        assert note.wine.region == "Burgundy"
        assert note.nose_notes == "Cherry and earth"
        assert note.palate_notes == ""


class TestAIProviderEnum:
    """Tests for AIProvider enum."""

    def test_anthropic_value(self) -> None:
        """Test Anthropic provider value."""
        assert AIProvider.ANTHROPIC.value == "anthropic"

    def test_openai_value(self) -> None:
        """Test OpenAI provider value."""
        assert AIProvider.OPENAI.value == "openai"

    def test_from_string(self) -> None:
        """Test creating provider from string."""
        assert AIProvider("anthropic") == AIProvider.ANTHROPIC
        assert AIProvider("openai") == AIProvider.OPENAI
