"""AI client interface and provider abstraction."""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any

from pydantic import BaseModel

from wine_agent.core.schema import TastingNote


# Fields that should be empty strings instead of null
# These match the TastingNote schema where str fields have default=""
_STRING_FIELDS_BY_PATH = {
    "wine": ["producer", "cuvee", "country", "region", "subregion", "appellation", "vineyard"],
    "context": ["location", "glassware", "companions", "occasion", "food_pairing", "mood"],
    "purchase": ["store"],
    "provenance": ["storage_notes"],
    "confidence": ["uncertainty_notes"],
    "faults": ["notes"],
    "readiness": ["notes"],
}

# Top-level string fields
_TOP_LEVEL_STRING_FIELDS = [
    "appearance_notes", "nose_notes", "palate_notes", "structure_notes",
    "finish_notes", "typicity_notes", "overall_notes", "conclusion",
]


def sanitize_ai_response(data: dict[str, Any]) -> dict[str, Any]:
    """
    Convert null values to empty strings for string fields.

    The AI often returns null for optional string fields, but our Pydantic
    models expect empty strings (str with default="") not None.

    Args:
        data: The parsed JSON dict from the AI.

    Returns:
        Sanitized dict with nulls converted to empty strings where appropriate.
    """
    result = data.copy()

    # Handle nested objects
    for parent_key, string_fields in _STRING_FIELDS_BY_PATH.items():
        if parent_key in result and isinstance(result[parent_key], dict):
            nested = result[parent_key].copy()
            for field in string_fields:
                if field in nested and nested[field] is None:
                    nested[field] = ""
            result[parent_key] = nested

    # Handle top-level string fields
    for field in _TOP_LEVEL_STRING_FIELDS:
        if field in result and result[field] is None:
            result[field] = ""

    return result


class AIProvider(str, Enum):
    """Supported AI providers."""

    ANTHROPIC = "anthropic"
    OPENAI = "openai"


class GenerationResult(BaseModel):
    """Result of an AI generation attempt."""

    success: bool
    raw_response: str
    parsed_json: dict[str, Any] | None = None
    tasting_note: TastingNote | None = None
    error_message: str | None = None
    repair_attempts: int = 0


class AIClient(ABC):
    """Abstract base class for AI providers."""

    provider: AIProvider
    model: str

    @abstractmethod
    def generate_structured_note(
        self,
        raw_text: str,
        hints: dict[str, Any] | None = None,
    ) -> GenerationResult:
        """
        Generate a structured tasting note from raw text.

        Args:
            raw_text: The unstructured tasting note text.
            hints: Optional hints to guide the AI (e.g., known producer, vintage).

        Returns:
            GenerationResult with the parsed TastingNote or error details.
        """
        pass

    @abstractmethod
    def repair_json(
        self,
        invalid_json: str,
        error_message: str,
    ) -> str:
        """
        Attempt to repair invalid JSON.

        Args:
            invalid_json: The malformed JSON string.
            error_message: The error message from the parser.

        Returns:
            The repaired JSON string.
        """
        pass


def get_ai_client(
    provider: AIProvider | str,
    api_key: str,
    model: str | None = None,
) -> AIClient:
    """
    Factory function to get an AI client for the specified provider.

    Args:
        provider: The AI provider to use.
        api_key: The API key for the provider.
        model: Optional model name override.

    Returns:
        An AIClient instance for the specified provider.

    Raises:
        ValueError: If the provider is not supported.
    """
    if isinstance(provider, str):
        provider = AIProvider(provider.lower())

    if provider == AIProvider.ANTHROPIC:
        from wine_agent.services.ai.providers.anthropic import AnthropicClient

        return AnthropicClient(api_key=api_key, model=model)
    elif provider == AIProvider.OPENAI:
        from wine_agent.services.ai.providers.openai import OpenAIClient

        return OpenAIClient(api_key=api_key, model=model)
    else:
        raise ValueError(f"Unsupported AI provider: {provider}")
