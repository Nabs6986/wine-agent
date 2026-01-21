"""Prompt templates for AI conversion."""

PROMPT_VERSION = "1.1"

# JSON Schema for the TastingNote output (simplified for AI)
TASTING_NOTE_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "wine": {
            "type": "object",
            "properties": {
                "producer": {"type": "string", "description": "Wine producer/winery name"},
                "cuvee": {"type": "string", "description": "Wine name/cuvée"},
                "vintage": {"type": ["integer", "null"], "description": "Vintage year or null if unknown"},
                "country": {"type": "string", "description": "Country of origin"},
                "region": {"type": "string", "description": "Wine region"},
                "subregion": {"type": "string", "description": "Subregion if applicable"},
                "appellation": {"type": "string", "description": "Appellation/AOC/DOC"},
                "vineyard": {"type": "string", "description": "Specific vineyard if mentioned"},
                "grapes": {"type": "array", "items": {"type": "string"}, "description": "Grape varieties"},
                "color": {"type": ["string", "null"], "enum": ["red", "white", "rose", "orange", "sparkling", "fortified", "other", None]},
                "style": {"type": ["string", "null"], "enum": ["still", "sparkling", "fortified", "other", None]},
                "sweetness": {"type": ["string", "null"], "enum": ["bone_dry", "dry", "off_dry", "medium", "sweet", "very_sweet", None]},
                "alcohol_percent": {"type": ["number", "null"]},
                "closure": {"type": ["string", "null"], "enum": ["cork", "screwcap", "synthetic", "other", None]},
            },
        },
        "purchase": {
            "type": "object",
            "properties": {
                "price_usd": {"type": ["number", "null"]},
                "store": {"type": "string"},
                "purchase_date": {"type": ["string", "null"], "format": "date"},
            },
        },
        "context": {
            "type": "object",
            "properties": {
                "tasting_date": {"type": ["string", "null"], "format": "date"},
                "location": {"type": "string"},
                "glassware": {"type": "string"},
                "decant": {"type": ["string", "null"], "enum": ["none", "splash", "short", "long", None]},
                "decant_minutes": {"type": ["integer", "null"]},
                "serving_temp_c": {"type": ["number", "null"]},
                "companions": {"type": "string"},
                "occasion": {"type": "string"},
                "food_pairing": {"type": "string"},
                "mood": {"type": "string"},
            },
        },
        "provenance": {
            "type": "object",
            "properties": {
                "bottle_condition": {"type": ["string", "null"], "enum": ["pristine", "suspected_heat", "compromised", "unknown", None]},
                "storage_notes": {"type": "string"},
            },
        },
        "confidence": {
            "type": "object",
            "properties": {
                "level": {"type": "string", "enum": ["low", "medium", "high"]},
                "uncertainty_notes": {"type": "string", "description": "Note any uncertain or inferred information"},
            },
        },
        "faults": {
            "type": "object",
            "properties": {
                "present": {"type": "boolean"},
                "suspected": {"type": "array", "items": {"type": "string"}, "description": "e.g., TCA, oxidation, VA, Brett"},
                "notes": {"type": "string"},
            },
        },
        "readiness": {
            "type": "object",
            "properties": {
                "drink_or_hold": {"type": "string", "enum": ["drink", "hold", "unsure"]},
                "window_start_year": {"type": ["integer", "null"]},
                "window_end_year": {"type": ["integer", "null"]},
                "notes": {"type": "string"},
            },
        },
        "scores": {
            "type": "object",
            "properties": {
                "subscores": {
                    "type": "object",
                    "properties": {
                        "appearance": {"type": "integer", "minimum": 0, "maximum": 2},
                        "nose": {"type": "integer", "minimum": 0, "maximum": 12},
                        "palate": {"type": "integer", "minimum": 0, "maximum": 20},
                        "structure_balance": {"type": "integer", "minimum": 0, "maximum": 20},
                        "finish": {"type": "integer", "minimum": 0, "maximum": 10},
                        "typicity_complexity": {"type": "integer", "minimum": 0, "maximum": 16},
                        "overall_judgment": {"type": "integer", "minimum": 0, "maximum": 20},
                    },
                },
                "personal_enjoyment": {"type": ["integer", "null"], "minimum": 0, "maximum": 10},
                "value_for_money": {"type": ["integer", "null"], "minimum": 0, "maximum": 10},
            },
        },
        "structure_levels": {
            "type": "object",
            "properties": {
                "acidity": {"type": ["string", "null"], "enum": ["low", "med_minus", "medium", "med_plus", "high", "n/a", None]},
                "tannin": {"type": ["string", "null"], "enum": ["low", "med_minus", "medium", "med_plus", "high", "n/a", None]},
                "body": {"type": ["string", "null"], "enum": ["light", "med_minus", "medium", "med_plus", "full", None]},
                "alcohol": {"type": ["string", "null"], "enum": ["low", "medium", "high", None]},
                "sweetness": {"type": ["string", "null"], "enum": ["dry", "off_dry", "medium", "sweet", None]},
                "intensity": {"type": ["string", "null"], "enum": ["low", "medium", "pronounced", None]},
                "oak": {"type": ["string", "null"], "enum": ["none", "subtle", "integrated", "dominant", None]},
            },
        },
        "descriptors": {
            "type": "object",
            "properties": {
                "primary_fruit": {"type": "array", "items": {"type": "string"}},
                "secondary": {"type": "array", "items": {"type": "string"}},
                "tertiary": {"type": "array", "items": {"type": "string"}},
                "non_fruit": {"type": "array", "items": {"type": "string"}},
                "texture": {"type": "array", "items": {"type": "string"}},
            },
        },
        "pairing": {
            "type": "object",
            "properties": {
                "suggested": {"type": "array", "items": {"type": "string"}},
                "avoid": {"type": "array", "items": {"type": "string"}},
            },
        },
        "appearance_notes": {"type": "string"},
        "nose_notes": {"type": "string"},
        "palate_notes": {"type": "string"},
        "structure_notes": {"type": "string"},
        "finish_notes": {"type": "string"},
        "typicity_notes": {"type": "string"},
        "overall_notes": {"type": "string"},
        "conclusion": {"type": "string"},
    },
}


SYSTEM_PROMPT = """You are an expert sommelier and wine critic assistant. Your task is to convert free-form wine tasting notes into a structured JSON format.

CRITICAL RULES:
1. NEVER invent information that is not present or clearly implied in the input
2. Use null for any fields you cannot determine from the text
3. Use empty strings "" for text fields where information is not provided
4. Use empty arrays [] for list fields where information is not provided
5. Mark uncertainty_notes with any information you had to infer or are uncertain about
6. Preserve the user's voice and terminology where possible in the notes fields

SCORING GUIDELINES (100-point system built from subscores):
- Appearance (0-2): Clarity, intensity, color appropriateness
- Nose (0-12): Intensity, complexity, cleanliness, development
- Palate (0-20): Flavor intensity, complexity, precision
- Structure & Balance (0-20): Integration of acidity/tannin/alcohol/body
- Finish (0-10): Length and quality of aftertaste
- Typicity & Complexity (0-16): True to variety/region, layers of flavor
- Overall Judgment (0-20): Holistic quality, memorability, craftsmanship

If the user hasn't explicitly scored the wine, make a reasonable estimate based on their descriptive language (e.g., "amazing", "disappointing", "good value").

QUALITY BAND REFERENCE:
- 0-69: Poor
- 70-79: Acceptable
- 80-89: Good
- 90-94: Very Good
- 95-100: Outstanding

Output ONLY valid JSON matching the schema. No additional text or explanation."""


CONVERSION_PROMPT_TEMPLATE = """Convert the following wine tasting notes into structured JSON format.

RAW TASTING NOTES:
{raw_text}

{hints_section}

You MUST use EXACTLY this JSON structure (use the exact field names shown):

{{
  "wine": {{
    "producer": "string - winery/producer name",
    "cuvee": "string - wine name/cuvee",
    "vintage": integer or null,
    "country": "string",
    "region": "string",
    "subregion": "string",
    "appellation": "string - AOC/DOC/AVA",
    "vineyard": "string",
    "grapes": ["array", "of", "grape", "varieties"],
    "color": "red" | "white" | "rose" | "orange" | "sparkling" | "fortified" | null,
    "style": "still" | "sparkling" | "fortified" | null,
    "sweetness": "bone_dry" | "dry" | "off_dry" | "medium" | "sweet" | "very_sweet" | null,
    "alcohol_percent": number or null
  }},
  "context": {{
    "tasting_date": "YYYY-MM-DD" or null,
    "location": "string",
    "occasion": "string",
    "food_pairing": "string",
    "companions": "string",
    "glassware": "string",
    "decant": "none" | "splash" | "short" | "long" | null,
    "decant_minutes": integer or null
  }},
  "scores": {{
    "subscores": {{
      "appearance": 0-2,
      "nose": 0-12,
      "palate": 0-20,
      "structure_balance": 0-20,
      "finish": 0-10,
      "typicity_complexity": 0-16,
      "overall_judgment": 0-20
    }},
    "personal_enjoyment": 0-10 or null
  }},
  "structure_levels": {{
    "acidity": "low" | "med_minus" | "medium" | "med_plus" | "high" | null,
    "tannin": "low" | "med_minus" | "medium" | "med_plus" | "high" | null,
    "body": "light" | "med_minus" | "medium" | "med_plus" | "full" | null,
    "alcohol": "low" | "medium" | "high" | null,
    "sweetness": "dry" | "off_dry" | "medium" | "sweet" | null,
    "intensity": "low" | "medium" | "pronounced" | null,
    "oak": "none" | "subtle" | "integrated" | "dominant" | null
  }},
  "readiness": {{
    "drink_or_hold": "drink" | "hold" | "unsure",
    "window_start_year": integer or null,
    "window_end_year": integer or null,
    "notes": "string"
  }},
  "descriptors": {{
    "primary_fruit": ["array", "of", "descriptors"],
    "secondary": ["array"],
    "tertiary": ["array"],
    "non_fruit": ["array"],
    "texture": ["array"]
  }},
  "appearance_notes": "string - visual description",
  "nose_notes": "string - aroma description",
  "palate_notes": "string - taste description",
  "structure_notes": "string - structure assessment",
  "finish_notes": "string - finish description",
  "overall_notes": "string - overall impression",
  "conclusion": "string - final summary"
}}

Output ONLY the JSON object, no markdown code blocks or additional text."""


REPAIR_PROMPT_TEMPLATE = """The following JSON is invalid and needs to be repaired.

INVALID JSON:
{invalid_json}

ERROR MESSAGE:
{error_message}

Please fix the JSON to make it valid. Common issues include:
- Missing or extra commas
- Unquoted strings
- Invalid escape sequences
- Trailing commas in arrays/objects
- Missing closing brackets

Output ONLY the corrected JSON, no explanation."""


def build_conversion_prompt(
    raw_text: str,
    hints: dict | None = None,
) -> str:
    """
    Build the conversion prompt with raw text and optional hints.

    Args:
        raw_text: The unstructured tasting note text.
        hints: Optional hints dict (e.g., {"producer": "...", "vintage": 2020}).

    Returns:
        The formatted prompt string.
    """
    hints_section = ""
    if hints:
        hints_lines = ["ADDITIONAL HINTS (verified information):"]
        for key, value in hints.items():
            hints_lines.append(f"- {key}: {value}")
        hints_section = "\n".join(hints_lines)

    return CONVERSION_PROMPT_TEMPLATE.format(
        raw_text=raw_text,
        hints_section=hints_section,
    )


def build_repair_prompt(invalid_json: str, error_message: str) -> str:
    """
    Build the JSON repair prompt.

    Args:
        invalid_json: The malformed JSON string.
        error_message: The error from the JSON parser.

    Returns:
        The formatted repair prompt.
    """
    return REPAIR_PROMPT_TEMPLATE.format(
        invalid_json=invalid_json,
        error_message=error_message,
    )
