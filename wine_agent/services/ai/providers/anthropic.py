"""Anthropic (Claude) AI provider implementation."""

import json
import logging
from typing import Any

from wine_agent.core.schema import TastingNote
from wine_agent.services.ai.client import AIClient, AIProvider, GenerationResult
from wine_agent.services.ai.prompts import (
    SYSTEM_PROMPT,
    build_conversion_prompt,
    build_repair_prompt,
)

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-sonnet-4-20250514"
MAX_REPAIR_ATTEMPTS = 2

# Fields that should be empty strings instead of null
# These match the TastingNote schema where str fields have default=""
STRING_FIELDS_BY_PATH = {
    "wine": ["producer", "cuvee", "country", "region", "subregion", "appellation", "vineyard"],
    "context": ["location", "glassware", "companions", "occasion", "food_pairing", "mood"],
    "purchase": ["store"],
    "provenance": ["storage_notes"],
    "confidence": ["uncertainty_notes"],
    "faults": ["notes"],
    "readiness": ["notes"],
    "pairing": [],
    "descriptors": [],
}

# Top-level string fields
TOP_LEVEL_STRING_FIELDS = [
    "appearance_notes", "nose_notes", "palate_notes", "structure_notes",
    "finish_notes", "typicity_notes", "overall_notes", "conclusion",
]


def _sanitize_nulls_to_empty_strings(data: dict[str, Any]) -> dict[str, Any]:
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
    for parent_key, string_fields in STRING_FIELDS_BY_PATH.items():
        if parent_key in result and isinstance(result[parent_key], dict):
            nested = result[parent_key].copy()
            for field in string_fields:
                if field in nested and nested[field] is None:
                    nested[field] = ""
            result[parent_key] = nested

    # Handle top-level string fields
    for field in TOP_LEVEL_STRING_FIELDS:
        if field in result and result[field] is None:
            result[field] = ""

    return result


class AnthropicClient(AIClient):
    """Anthropic Claude AI client."""

    provider = AIProvider.ANTHROPIC

    def __init__(self, api_key: str, model: str | None = None):
        """
        Initialize the Anthropic client.

        Args:
            api_key: Anthropic API key.
            model: Model name (defaults to claude-sonnet-4-20250514).
        """
        try:
            import anthropic
        except ImportError:
            raise ImportError(
                "anthropic package is required. Install with: pip install anthropic"
            )

        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model or DEFAULT_MODEL

    def generate_structured_note(
        self,
        raw_text: str,
        hints: dict[str, Any] | None = None,
    ) -> GenerationResult:
        """
        Generate a structured tasting note from raw text using Claude.

        Args:
            raw_text: The unstructured tasting note text.
            hints: Optional hints to guide the AI.

        Returns:
            GenerationResult with the parsed TastingNote or error details.
        """
        prompt = build_conversion_prompt(raw_text, hints)

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )

            raw_response = response.content[0].text
            logger.info(f"AI conversion received response ({len(raw_response)} chars)")
            logger.debug(f"Raw AI response: {raw_response[:1000]}...")

        except Exception as e:
            logger.error(f"Anthropic API error: {e}")
            return GenerationResult(
                success=False,
                raw_response="",
                error_message=f"API error: {str(e)}",
            )

        # Try to parse the JSON response
        return self._parse_and_validate(raw_response)

    def repair_json(self, invalid_json: str, error_message: str) -> str:
        """
        Attempt to repair invalid JSON using Claude.

        Args:
            invalid_json: The malformed JSON string.
            error_message: The error message from the parser.

        Returns:
            The repaired JSON string.
        """
        prompt = build_repair_prompt(invalid_json, error_message)

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text
        except Exception as e:
            logger.error(f"JSON repair API error: {e}")
            return invalid_json  # Return original on failure

    def _parse_and_validate(
        self,
        raw_response: str,
        repair_attempts: int = 0,
    ) -> GenerationResult:
        """
        Parse JSON response and validate against TastingNote schema.

        Args:
            raw_response: The raw JSON string from the AI.
            repair_attempts: Number of repair attempts made so far.

        Returns:
            GenerationResult with parsed data or error details.
        """
        # Clean up response (remove markdown code blocks if present)
        json_str = raw_response.strip()
        if json_str.startswith("```json"):
            json_str = json_str[7:]
        if json_str.startswith("```"):
            json_str = json_str[3:]
        if json_str.endswith("```"):
            json_str = json_str[:-3]
        json_str = json_str.strip()

        # Step 1: Try to parse JSON
        try:
            parsed_json = json.loads(json_str)
        except json.JSONDecodeError as e:
            error_msg = f"JSON parse error: {str(e)}"
            logger.warning(f"{error_msg} (attempt {repair_attempts + 1})")

            if repair_attempts < MAX_REPAIR_ATTEMPTS:
                # Try to repair the JSON
                repaired = self.repair_json(json_str, str(e))
                return self._parse_and_validate(
                    repaired, repair_attempts=repair_attempts + 1
                )

            return GenerationResult(
                success=False,
                raw_response=raw_response,
                error_message=error_msg,
                repair_attempts=repair_attempts,
            )

        # Step 2: Sanitize nulls to empty strings before Pydantic validation
        # The AI often returns null for optional string fields, but our schema expects ""
        sanitized_json = _sanitize_nulls_to_empty_strings(parsed_json)

        # Step 3: Validate against Pydantic model
        try:
            tasting_note = TastingNote.model_validate(sanitized_json)

            # Check if we got meaningful data (at least some wine identity info)
            has_wine_data = bool(
                tasting_note.wine.producer
                or tasting_note.wine.cuvee
                or tasting_note.wine.vintage
                or tasting_note.wine.region
            )
            has_notes_data = bool(
                tasting_note.nose_notes
                or tasting_note.palate_notes
                or tasting_note.appearance_notes
            )

            logger.info(
                f"AI conversion parsed: has_wine_data={has_wine_data}, "
                f"has_notes_data={has_notes_data}, "
                f"producer='{tasting_note.wine.producer}', "
                f"cuvee='{tasting_note.wine.cuvee}'"
            )

            if not has_wine_data and not has_notes_data:
                logger.warning("AI returned valid JSON but with no meaningful wine/notes data")
                logger.debug(f"Parsed JSON keys: {list(parsed_json.keys())}")
                if "wine" in parsed_json:
                    logger.debug(f"Wine data: {parsed_json['wine']}")

            return GenerationResult(
                success=True,
                raw_response=raw_response,
                parsed_json=parsed_json,
                tasting_note=tasting_note,
                repair_attempts=repair_attempts,
            )
        except Exception as e:
            error_msg = f"Validation error: {str(e)}"
            logger.warning(f"{error_msg} (attempt {repair_attempts + 1})")

            if repair_attempts < MAX_REPAIR_ATTEMPTS:
                # Try to fix validation errors by re-prompting
                repaired = self.repair_json(
                    json.dumps(parsed_json, indent=2),
                    f"Pydantic validation failed: {str(e)}",
                )
                return self._parse_and_validate(
                    repaired, repair_attempts=repair_attempts + 1
                )

            return GenerationResult(
                success=False,
                raw_response=raw_response,
                parsed_json=parsed_json,
                error_message=error_msg,
                repair_attempts=repair_attempts,
            )
