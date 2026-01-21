"""Enums for wine tasting note fields."""

from enum import Enum


class WineColor(str, Enum):
    """Wine color classification."""

    RED = "red"
    WHITE = "white"
    ROSE = "rose"
    ORANGE = "orange"
    SPARKLING = "sparkling"
    FORTIFIED = "fortified"
    OTHER = "other"


class WineStyle(str, Enum):
    """Wine style classification."""

    STILL = "still"
    SPARKLING = "sparkling"
    FORTIFIED = "fortified"
    OTHER = "other"


class Sweetness(str, Enum):
    """Wine sweetness level."""

    BONE_DRY = "bone_dry"
    DRY = "dry"
    OFF_DRY = "off_dry"
    MEDIUM = "medium"
    SWEET = "sweet"
    VERY_SWEET = "very_sweet"


class Closure(str, Enum):
    """Bottle closure type."""

    CORK = "cork"
    SCREWCAP = "screwcap"
    SYNTHETIC = "synthetic"
    OTHER = "other"


class DecantLevel(str, Enum):
    """Decanting level."""

    NONE = "none"
    SPLASH = "splash"
    SHORT = "short"
    LONG = "long"


class BottleCondition(str, Enum):
    """Bottle condition/provenance."""

    PRISTINE = "pristine"
    SUSPECTED_HEAT = "suspected_heat"
    COMPROMISED = "compromised"
    UNKNOWN = "unknown"


class ConfidenceLevel(str, Enum):
    """Confidence level in tasting assessment."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class DrinkOrHold(str, Enum):
    """Drink or hold recommendation."""

    DRINK = "drink"
    HOLD = "hold"
    UNSURE = "unsure"


class QualityBand(str, Enum):
    """Quality band based on total score."""

    POOR = "poor"  # 0-69
    ACCEPTABLE = "acceptable"  # 70-79
    GOOD = "good"  # 80-89
    VERY_GOOD = "very_good"  # 90-94
    OUTSTANDING = "outstanding"  # 95-100


class StructureLevel(str, Enum):
    """Structure level (acidity, tannin)."""

    LOW = "low"
    MED_MINUS = "med_minus"
    MEDIUM = "medium"
    MED_PLUS = "med_plus"
    HIGH = "high"
    NA = "n/a"


class BodyLevel(str, Enum):
    """Body level."""

    LIGHT = "light"
    MED_MINUS = "med_minus"
    MEDIUM = "medium"
    MED_PLUS = "med_plus"
    FULL = "full"


class AlcoholLevel(str, Enum):
    """Perceived alcohol level."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class SweetnessLevel(str, Enum):
    """Perceived sweetness level on palate."""

    DRY = "dry"
    OFF_DRY = "off_dry"
    MEDIUM = "medium"
    SWEET = "sweet"


class IntensityLevel(str, Enum):
    """Intensity level (nose/palate)."""

    LOW = "low"
    MEDIUM = "medium"
    PRONOUNCED = "pronounced"


class OakLevel(str, Enum):
    """Oak integration level."""

    NONE = "none"
    SUBTLE = "subtle"
    INTEGRATED = "integrated"
    DOMINANT = "dominant"


class NoteStatus(str, Enum):
    """Tasting note status."""

    DRAFT = "draft"
    PUBLISHED = "published"


class NoteSource(str, Enum):
    """Source of the tasting note."""

    MANUAL = "manual"
    INBOX_CONVERTED = "inbox-converted"
    IMPORTED = "imported"
