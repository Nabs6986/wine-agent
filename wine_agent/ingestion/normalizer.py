"""
Data Normalizer Module
======================

Cleans and standardizes extracted wine data for consistent
storage and matching.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from wine_agent.ingestion.adapters.base import ExtractedListing


@dataclass
class NormalizedListing:
    """
    Cleaned and standardized wine listing data.

    All fields are in canonical form ready for entity resolution.
    """

    # Wine identity
    producer_name: str | None = None
    wine_name: str | None = None
    vintage_year: int | None = None

    # Location
    country: str | None = None
    region: str | None = None
    sub_region: str | None = None
    appellation: str | None = None

    # Wine characteristics
    grapes: list[str] = field(default_factory=list)
    color: str | None = None  # red, white, rosé, orange, sparkling
    style: str | None = None  # still, sparkling, fortified

    # Technical details
    bottle_size_ml: int = 750
    abv: float | None = None

    # Pricing
    price: float | None = None
    currency: str | None = None

    # Source information
    url: str = ""
    source_name: str = ""

    # Original extracted data (for reference)
    original_title: str | None = None


class Normalizer:
    """
    Normalizes extracted wine data into canonical forms.

    Handles:
    - Region name standardization (e.g., "burgundy" -> "Bourgogne")
    - Grape variety normalization (e.g., "cab" -> "Cabernet Sauvignon")
    - ABV parsing from various formats
    - Vintage year validation and parsing
    - Bottle size standardization
    """

    # Region aliases: maps common variations to canonical names
    REGION_ALIASES: dict[str, str] = {
        # France
        "burgundy": "Bourgogne",
        "bordeaux": "Bordeaux",
        "champagne": "Champagne",
        "rhone": "Rhône",
        "rhône": "Rhône",
        "rhone valley": "Rhône",
        "loire": "Loire",
        "loire valley": "Loire",
        "alsace": "Alsace",
        "provence": "Provence",
        "languedoc": "Languedoc-Roussillon",
        "roussillon": "Languedoc-Roussillon",
        "languedoc-roussillon": "Languedoc-Roussillon",
        "beaujolais": "Beaujolais",
        "cote de nuits": "Côte de Nuits",
        "côte de nuits": "Côte de Nuits",
        "cote de beaune": "Côte de Beaune",
        "côte de beaune": "Côte de Beaune",
        "chablis": "Chablis",
        "sauternes": "Sauternes",
        "medoc": "Médoc",
        "médoc": "Médoc",
        "pauillac": "Pauillac",
        "margaux": "Margaux",
        "saint-julien": "Saint-Julien",
        "saint julien": "Saint-Julien",
        "st julien": "Saint-Julien",
        "saint-emilion": "Saint-Émilion",
        "saint emilion": "Saint-Émilion",
        "st emilion": "Saint-Émilion",
        "pomerol": "Pomerol",
        "graves": "Graves",
        "pessac-leognan": "Pessac-Léognan",
        "pessac leognan": "Pessac-Léognan",

        # Italy
        "piedmont": "Piemonte",
        "piemonte": "Piemonte",
        "tuscany": "Toscana",
        "toscana": "Toscana",
        "veneto": "Veneto",
        "sicily": "Sicilia",
        "sicilia": "Sicilia",
        "barolo": "Barolo",
        "barbaresco": "Barbaresco",
        "chianti": "Chianti",
        "chianti classico": "Chianti Classico",
        "brunello di montalcino": "Brunello di Montalcino",
        "vino nobile di montepulciano": "Vino Nobile di Montepulciano",
        "amarone": "Amarone della Valpolicella",

        # Spain
        "rioja": "Rioja",
        "ribera del duero": "Ribera del Duero",
        "priorat": "Priorat",
        "rias baixas": "Rías Baixas",
        "rías baixas": "Rías Baixas",
        "jerez": "Jerez",
        "sherry": "Jerez",

        # Germany
        "mosel": "Mosel",
        "rheingau": "Rheingau",
        "pfalz": "Pfalz",
        "rheinhessen": "Rheinhessen",

        # USA
        "napa": "Napa Valley",
        "napa valley": "Napa Valley",
        "sonoma": "Sonoma",
        "sonoma county": "Sonoma",
        "willamette": "Willamette Valley",
        "willamette valley": "Willamette Valley",
        "santa barbara": "Santa Barbara",
        "paso robles": "Paso Robles",
        "russian river": "Russian River Valley",
        "russian river valley": "Russian River Valley",

        # Australia
        "barossa": "Barossa Valley",
        "barossa valley": "Barossa Valley",
        "mclaren vale": "McLaren Vale",
        "hunter valley": "Hunter Valley",
        "margaret river": "Margaret River",
        "yarra valley": "Yarra Valley",
        "coonawarra": "Coonawarra",

        # New Zealand
        "marlborough": "Marlborough",
        "central otago": "Central Otago",
        "hawkes bay": "Hawke's Bay",
        "hawke's bay": "Hawke's Bay",

        # South America
        "mendoza": "Mendoza",
        "maipo": "Maipo Valley",
        "maipo valley": "Maipo Valley",
        "colchagua": "Colchagua Valley",
        "colchagua valley": "Colchagua Valley",

        # South Africa
        "stellenbosch": "Stellenbosch",
        "franschhoek": "Franschhoek",
        "swartland": "Swartland",

        # Portugal
        "douro": "Douro",
        "porto": "Porto",
        "port": "Porto",
        "dao": "Dão",
        "dão": "Dão",
        "alentejo": "Alentejo",
    }

    # Grape variety aliases
    GRAPE_ALIASES: dict[str, str] = {
        # Red grapes
        "cab": "Cabernet Sauvignon",
        "cab sauv": "Cabernet Sauvignon",
        "cabernet": "Cabernet Sauvignon",
        "cabernet sauvignon": "Cabernet Sauvignon",
        "cab franc": "Cabernet Franc",
        "cabernet franc": "Cabernet Franc",
        "merlot": "Merlot",
        "pinot": "Pinot Noir",
        "pinot noir": "Pinot Noir",
        "syrah": "Syrah",
        "shiraz": "Shiraz",
        "grenache": "Grenache",
        "garnacha": "Grenache",
        "tempranillo": "Tempranillo",
        "temp": "Tempranillo",
        "tinto fino": "Tempranillo",
        "sangiovese": "Sangiovese",
        "nebbiolo": "Nebbiolo",
        "barbera": "Barbera",
        "malbec": "Malbec",
        "zinfandel": "Zinfandel",
        "zin": "Zinfandel",
        "primitivo": "Primitivo",
        "petit verdot": "Petit Verdot",
        "mourvèdre": "Mourvèdre",
        "mourvedre": "Mourvèdre",
        "monastrell": "Mourvèdre",
        "carmenere": "Carménère",
        "carménère": "Carménère",
        "gamay": "Gamay",
        "cinsault": "Cinsault",
        "carignan": "Carignan",
        "touriga nacional": "Touriga Nacional",
        "touriga franca": "Touriga Franca",

        # White grapes
        "chard": "Chardonnay",
        "chardonnay": "Chardonnay",
        "sauv blanc": "Sauvignon Blanc",
        "sauvignon": "Sauvignon Blanc",
        "sauvignon blanc": "Sauvignon Blanc",
        "riesling": "Riesling",
        "pinot grigio": "Pinot Grigio",
        "pinot gris": "Pinot Gris",
        "gewurztraminer": "Gewürztraminer",
        "gewürztraminer": "Gewürztraminer",
        "viognier": "Viognier",
        "chenin": "Chenin Blanc",
        "chenin blanc": "Chenin Blanc",
        "semillon": "Sémillon",
        "sémillon": "Sémillon",
        "muscadet": "Muscadet",
        "albarino": "Albariño",
        "albariño": "Albariño",
        "gruner veltliner": "Grüner Veltliner",
        "grüner veltliner": "Grüner Veltliner",
        "vermentino": "Vermentino",
        "trebbiano": "Trebbiano",
        "marsanne": "Marsanne",
        "roussanne": "Roussanne",
        "muscat": "Muscat",
        "moscato": "Moscato",
        "torrontes": "Torrontés",
        "torrontés": "Torrontés",
        "pinot meunier": "Pinot Meunier",
        "melon de bourgogne": "Melon de Bourgogne",
    }

    # Color normalization
    COLOR_ALIASES: dict[str, str] = {
        "red": "red",
        "rouge": "red",
        "tinto": "red",
        "rosso": "red",
        "white": "white",
        "blanc": "white",
        "blanco": "white",
        "bianco": "white",
        "rosé": "rosé",
        "rose": "rosé",
        "rosado": "rosé",
        "pink": "rosé",
        "orange": "orange",
        "amber": "orange",
        "sparkling": "sparkling",
        "champagne": "sparkling",
        "cava": "sparkling",
        "prosecco": "sparkling",
        "cremant": "sparkling",
        "crémant": "sparkling",
    }

    # Style normalization
    STYLE_ALIASES: dict[str, str] = {
        "still": "still",
        "sparkling": "sparkling",
        "champagne": "sparkling",
        "fortified": "fortified",
        "port": "fortified",
        "porto": "fortified",
        "sherry": "fortified",
        "madeira": "fortified",
        "dessert": "dessert",
        "sweet": "dessert",
    }

    # Bottle size patterns and their ml values
    BOTTLE_SIZE_PATTERNS: list[tuple[re.Pattern[str], int]] = [
        (re.compile(r"(?:^|\s)375\s*(?:ml)?(?:\s|$)", re.I), 375),   # Half bottle
        (re.compile(r"(?:^|\s)500\s*(?:ml)?(?:\s|$)", re.I), 500),   # 500ml
        (re.compile(r"(?:^|\s)750\s*(?:ml)?(?:\s|$)", re.I), 750),   # Standard
        (re.compile(r"(?:^|\s)1\.?5\s*(?:l|liter|litre)s?(?:\s|$)", re.I), 1500),  # Magnum
        (re.compile(r"(?:^|\s)1500\s*(?:ml)?(?:\s|$)", re.I), 1500), # Magnum
        (re.compile(r"(?:^|\s)3\s*(?:l|liter|litre)s?(?:\s|$)", re.I), 3000),  # Double Magnum
        (re.compile(r"(?:^|\s)3000\s*(?:ml)?(?:\s|$)", re.I), 3000),
        (re.compile(r"magnum", re.I), 1500),
        (re.compile(r"half\s*bottle", re.I), 375),
        (re.compile(r"demi", re.I), 375),
    ]

    # ABV extraction patterns
    ABV_PATTERNS: list[re.Pattern[str]] = [
        re.compile(r"(\d+(?:\.\d+)?)\s*%\s*(?:abv|alc|vol)?", re.I),
        re.compile(r"(?:abv|alc|alcohol)[:\s]*(\d+(?:\.\d+)?)\s*%?", re.I),
        re.compile(r"(\d+(?:\.\d+)?)\s*(?:degrees|°)", re.I),
    ]

    def normalize_listing(self, extracted: ExtractedListing) -> NormalizedListing:
        """
        Normalize an extracted listing.

        Args:
            extracted: Raw extracted listing from an adapter

        Returns:
            NormalizedListing with cleaned and standardized data
        """
        normalized = NormalizedListing(
            url=extracted.url,
            source_name=extracted.source_name,
            original_title=extracted.title,
        )

        # Normalize producer name
        producer = extracted.get_value("producer_name")
        if producer:
            normalized.producer_name = self._clean_string(producer)

        # Normalize wine name
        wine = extracted.get_value("wine_name")
        if wine:
            normalized.wine_name = self._clean_string(wine)

        # Parse vintage
        vintage = extracted.get_value("vintage_year")
        normalized.vintage_year = self.parse_vintage(vintage)

        # Normalize location fields
        normalized.country = self._clean_string(extracted.get_value("country"))
        normalized.region = self.normalize_region(extracted.get_value("region"))
        normalized.sub_region = self.normalize_region(extracted.get_value("sub_region"))
        normalized.appellation = self._clean_string(extracted.get_value("appellation"))

        # Normalize grapes
        grapes = extracted.get_value("grapes")
        normalized.grapes = self.normalize_grapes(grapes)

        # Normalize color and style
        color = extracted.get_value("color")
        if color:
            normalized.color = self.COLOR_ALIASES.get(color.lower().strip(), color.lower())

        style = extracted.get_value("style")
        if style:
            normalized.style = self.STYLE_ALIASES.get(style.lower().strip(), style.lower())

        # Parse bottle size
        bottle_size = extracted.get_value("bottle_size_ml")
        if bottle_size:
            try:
                normalized.bottle_size_ml = int(bottle_size)
            except (TypeError, ValueError):
                # Try to parse from string
                normalized.bottle_size_ml = self._parse_bottle_size(str(bottle_size))

        # Parse ABV
        abv = extracted.get_value("abv")
        normalized.abv = self.parse_abv(abv)

        # Parse price
        price = extracted.get_value("price")
        if price is not None:
            try:
                normalized.price = float(price)
            except (TypeError, ValueError):
                pass

        currency = extracted.get_value("currency")
        if currency:
            normalized.currency = currency.upper().strip()

        return normalized

    def _clean_string(self, value: Any) -> str | None:
        """Clean and normalize a string value."""
        if value is None:
            return None
        s = str(value).strip()
        # Normalize whitespace
        s = re.sub(r"\s+", " ", s)
        return s if s else None

    def normalize_region(self, region: str | None) -> str | None:
        """
        Normalize a region name to its canonical form.

        Args:
            region: Raw region name

        Returns:
            Canonical region name, or original if no alias found
        """
        if region is None:
            return None

        cleaned = self._clean_string(region)
        if cleaned is None:
            return None

        # Look up alias (case-insensitive)
        canonical = self.REGION_ALIASES.get(cleaned.lower())
        return canonical if canonical else cleaned

    def normalize_grapes(self, grapes: list[str] | str | None) -> list[str]:
        """
        Normalize grape variety names.

        Args:
            grapes: List of grapes, comma-separated string, or None

        Returns:
            List of canonical grape names
        """
        if grapes is None:
            return []

        # Convert to list if string
        if isinstance(grapes, str):
            # Split on common delimiters
            grape_list = re.split(r"[,;/&]|\band\b", grapes)
        else:
            grape_list = grapes

        normalized = []
        for grape in grape_list:
            cleaned = self._clean_string(grape)
            if cleaned:
                # Look up alias
                canonical = self.GRAPE_ALIASES.get(cleaned.lower())
                normalized.append(canonical if canonical else cleaned)

        return normalized

    def parse_abv(self, abv_str: str | float | int | None) -> float | None:
        """
        Parse ABV from various formats.

        Args:
            abv_str: ABV value (e.g., "13.5%", "13.5", 13.5)

        Returns:
            ABV as float, or None if parsing fails
        """
        if abv_str is None:
            return None

        # If already numeric
        if isinstance(abv_str, (int, float)):
            abv = float(abv_str)
            # Sanity check: ABV should be between 0 and 25
            if 0 < abv <= 25:
                return abv
            return None

        # Try to extract from string
        s = str(abv_str)
        for pattern in self.ABV_PATTERNS:
            match = pattern.search(s)
            if match:
                try:
                    abv = float(match.group(1))
                    if 0 < abv <= 25:
                        return abv
                except (ValueError, IndexError):
                    continue

        return None

    def parse_vintage(self, vintage_str: str | int | None) -> int | None:
        """
        Parse vintage year from various formats.

        Args:
            vintage_str: Vintage value (e.g., "2019", 2019, "NV")

        Returns:
            Vintage year as int, or None for non-vintage wines
        """
        if vintage_str is None:
            return None

        # Handle "NV" or "Non-Vintage"
        if isinstance(vintage_str, str):
            if vintage_str.upper() in ("NV", "N/V", "NON-VINTAGE", "NONVINTAGE"):
                return None

        # Try to convert to int
        try:
            year = int(vintage_str)
            # Sanity check: vintage should be reasonable
            if 1800 <= year <= 2100:
                return year
        except (TypeError, ValueError):
            pass

        # Try to extract 4-digit year from string
        if isinstance(vintage_str, str):
            match = re.search(r"\b(19|20)\d{2}\b", vintage_str)
            if match:
                return int(match.group())

        return None

    def _parse_bottle_size(self, size_str: str) -> int:
        """
        Parse bottle size from string.

        Args:
            size_str: Size string (e.g., "750ml", "1.5L", "Magnum")

        Returns:
            Size in ml, defaults to 750
        """
        for pattern, ml in self.BOTTLE_SIZE_PATTERNS:
            if pattern.search(size_str):
                return ml
        return 750  # Default to standard bottle
