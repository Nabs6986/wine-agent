"""OpenAI AI provider implementation."""

import json
import logging
from typing import Any

from wine_agent.core.schema import TastingNote
from wine_agent.services.ai.client import AIClient, AIProvider, GenerationResult, sanitize_ai_response
from wine_agent.services.ai.prompts import (
    SYSTEM_PROMPT,
    build_conversion_prompt,
    build_repair_prompt,
)

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "gpt-4o"
MAX_REPAIR_ATTEMPTS = 2


class OpenAIClient(AIClient):
    """OpenAI GPT AI client."""

    provider = AIProvider.OPENAI

    def __init__(self, api_key: str, model: str | None = None):
        """
        Initialize the OpenAI client.

        Args:
            api_key: OpenAI API key.
            model: Model name (defaults to gpt-4o).
        """
        try:
            import openai
        except ImportError:
            raise ImportError(
                "openai package is required. Install with: pip install openai"
            )

        self.client = openai.OpenAI(api_key=api_key)
        self.model = model or DEFAULT_MODEL

    def generate_structured_note(
        self,
        raw_text: str,
        hints: dict[str, Any] | None = None,
    ) -> GenerationResult:
        """
        Generate a structured tasting note from raw text using GPT.

        Args:
            raw_text: The unstructured tasting note text.
            hints: Optional hints to guide the AI.

        Returns:
            GenerationResult with the parsed TastingNote or error details.
        """
        prompt = build_conversion_prompt(raw_text, hints)

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                max_tokens=4096,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
            )

            raw_response = response.choices[0].message.content or ""
            logger.debug(f"Raw AI response: {raw_response[:500]}...")

        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            return GenerationResult(
                success=False,
                raw_response="",
                error_message=f"API error: {str(e)}",
            )

        # Try to parse the JSON response
        return self._parse_and_validate(raw_response)

    def repair_json(self, invalid_json: str, error_message: str) -> str:
        """
        Attempt to repair invalid JSON using GPT.

        Args:
            invalid_json: The malformed JSON string.
            error_message: The error message from the parser.

        Returns:
            The repaired JSON string.
        """
        prompt = build_repair_prompt(invalid_json, error_message)

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
            )
            return response.choices[0].message.content or invalid_json
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
        sanitized_json = sanitize_ai_response(parsed_json)

        # Step 3: Validate against Pydantic model
        try:
            tasting_note = TastingNote.model_validate(sanitized_json)
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
