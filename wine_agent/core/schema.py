"""Canonical Pydantic v2 models for Wine Agent tasting notes."""

from datetime import UTC, date, datetime
from typing import Annotated
from uuid import UUID, uuid4


def _utc_now() -> datetime:
    """Return current UTC datetime (timezone-aware)."""
    return datetime.now(UTC)

from pydantic import BaseModel, Field, field_validator, model_validator

from wine_agent.core.enums import (
    AlcoholLevel,
    BodyLevel,
    BottleCondition,
    Closure,
    ConfidenceLevel,
    DecantLevel,
    DrinkOrHold,
    IntensityLevel,
    NoteSource,
    NoteStatus,
    OakLevel,
    QualityBand,
    StructureLevel,
    Sweetness,
    SweetnessLevel,
    WineColor,
    WineStyle,
)
from wine_agent.core.scoring import calculate_total_score, determine_quality_band


class WineIdentity(BaseModel):
    """Wine identification information."""

    producer: str = ""
    cuvee: str = ""
    vintage: int | None = None
    country: str = ""
    region: str = ""
    subregion: str = ""
    appellation: str = ""
    vineyard: str = ""
    grapes: list[str] = Field(default_factory=list)
    color: WineColor | None = None
    style: WineStyle | None = None
    sweetness: Sweetness | None = None
    alcohol_percent: float | None = None
    closure: Closure | None = None
    bottle_size_ml: int = 750


class PurchaseContext(BaseModel):
    """Purchase information."""

    price_usd: float | None = None
    store: str = ""
    purchase_date: date | None = None


class TastingContext(BaseModel):
    """Context surrounding the tasting."""

    tasting_date: date | None = None
    location: str = ""
    glassware: str = ""
    decant: DecantLevel | None = None
    decant_minutes: int | None = None
    serving_temp_c: float | None = None
    companions: str = ""
    occasion: str = ""
    food_pairing: str = ""
    mood: str = ""


class Provenance(BaseModel):
    """Bottle provenance and storage information."""

    bottle_condition: BottleCondition | None = None
    storage_notes: str = ""


class Confidence(BaseModel):
    """Confidence level in assessment."""

    level: ConfidenceLevel = ConfidenceLevel.MEDIUM
    uncertainty_notes: str = ""


class Faults(BaseModel):
    """Wine faults detection."""

    present: bool = False
    suspected: list[str] = Field(default_factory=list)
    notes: str = ""


class Readiness(BaseModel):
    """Drink/hold recommendation and aging window."""

    drink_or_hold: DrinkOrHold = DrinkOrHold.DRINK
    window_start_year: int | None = None
    window_end_year: int | None = None
    notes: str = ""


class SubScores(BaseModel):
    """Individual scoring components (100-point system)."""

    appearance: Annotated[int, Field(ge=0, le=2)] = 0
    nose: Annotated[int, Field(ge=0, le=12)] = 0
    palate: Annotated[int, Field(ge=0, le=20)] = 0
    structure_balance: Annotated[int, Field(ge=0, le=20)] = 0
    finish: Annotated[int, Field(ge=0, le=10)] = 0
    typicity_complexity: Annotated[int, Field(ge=0, le=16)] = 0
    overall_judgment: Annotated[int, Field(ge=0, le=20)] = 0


class Scores(BaseModel):
    """Complete scoring information."""

    system: str = "wine-agent-100"
    subscores: SubScores = Field(default_factory=SubScores)
    total: Annotated[int, Field(ge=0, le=100)] = 0
    quality_band: QualityBand | None = None
    personal_enjoyment: Annotated[int, Field(ge=0, le=10)] | None = None
    value_for_money: Annotated[int, Field(ge=0, le=10)] | None = None

    @model_validator(mode="after")
    def compute_total_and_band(self) -> "Scores":
        """Compute total score and quality band from subscores."""
        self.total = calculate_total_score(self.subscores)
        self.quality_band = determine_quality_band(self.total)
        return self


class StructureLevels(BaseModel):
    """Wine structure assessment."""

    acidity: StructureLevel | None = None
    tannin: StructureLevel | None = None
    body: BodyLevel | None = None
    alcohol: AlcoholLevel | None = None
    sweetness: SweetnessLevel | None = None
    intensity: IntensityLevel | None = None
    oak: OakLevel | None = None


class Descriptors(BaseModel):
    """Aroma and flavor descriptors."""

    primary_fruit: list[str] = Field(default_factory=list)
    secondary: list[str] = Field(default_factory=list)
    tertiary: list[str] = Field(default_factory=list)
    non_fruit: list[str] = Field(default_factory=list)
    texture: list[str] = Field(default_factory=list)


class Pairing(BaseModel):
    """Food pairing suggestions."""

    suggested: list[str] = Field(default_factory=list)
    avoid: list[str] = Field(default_factory=list)


class Links(BaseModel):
    """External references and links."""

    producer_site: str = ""
    importer: str = ""
    references: list[str] = Field(default_factory=list)


class InboxItem(BaseModel):
    """
    Raw, unstructured tasting note captured in the inbox.

    Represents the initial capture of free-form text that will later
    be converted to a structured TastingNote via AI processing.
    """

    id: UUID = Field(default_factory=uuid4)
    raw_text: str
    created_at: datetime = Field(default_factory=_utc_now)
    updated_at: datetime = Field(default_factory=_utc_now)
    converted: bool = False
    conversion_run_id: UUID | None = None
    tags: list[str] = Field(default_factory=list)

    @field_validator("raw_text")
    @classmethod
    def raw_text_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("raw_text cannot be empty")
        return v


class TastingNote(BaseModel):
    """
    Structured wine tasting note (draft or published).

    This is the canonical schema for a complete tasting note,
    containing wine identity, context, scores, and descriptors.
    """

    id: UUID = Field(default_factory=uuid4)
    template_version: str = "1.0"
    tags: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=_utc_now)
    updated_at: datetime = Field(default_factory=_utc_now)
    source: NoteSource = NoteSource.MANUAL
    status: NoteStatus = NoteStatus.DRAFT
    inbox_item_id: UUID | None = None

    wine: WineIdentity = Field(default_factory=WineIdentity)
    purchase: PurchaseContext = Field(default_factory=PurchaseContext)
    context: TastingContext = Field(default_factory=TastingContext)
    provenance: Provenance = Field(default_factory=Provenance)
    confidence: Confidence = Field(default_factory=Confidence)
    faults: Faults = Field(default_factory=Faults)
    readiness: Readiness = Field(default_factory=Readiness)
    scores: Scores = Field(default_factory=Scores)
    structure_levels: StructureLevels = Field(default_factory=StructureLevels)
    descriptors: Descriptors = Field(default_factory=Descriptors)
    pairing: Pairing = Field(default_factory=Pairing)
    links: Links = Field(default_factory=Links)

    appearance_notes: str = ""
    nose_notes: str = ""
    palate_notes: str = ""
    structure_notes: str = ""
    finish_notes: str = ""
    typicity_notes: str = ""
    overall_notes: str = ""
    conclusion: str = ""


class AIConversionRun(BaseModel):
    """
    Record of an AI conversion attempt.

    Stores traceability information for AI-assisted conversion
    of raw inbox text to structured tasting notes.
    """

    id: UUID = Field(default_factory=uuid4)
    inbox_item_id: UUID
    created_at: datetime = Field(default_factory=_utc_now)

    provider: str
    model: str
    prompt_version: str
    input_hash: str
    raw_input: str
    raw_response: str
    parsed_json: dict | None = None

    success: bool = False
    error_message: str | None = None
    repair_attempts: int = 0

    resulting_note_id: UUID | None = None


class Revision(BaseModel):
    """
    Revision history entry for a tasting note.

    Tracks changes made to published notes for audit purposes.
    """

    id: UUID = Field(default_factory=uuid4)
    tasting_note_id: UUID
    revision_number: int
    created_at: datetime = Field(default_factory=_utc_now)

    changed_fields: list[str] = Field(default_factory=list)
    previous_snapshot: dict
    new_snapshot: dict
    change_reason: str = ""
