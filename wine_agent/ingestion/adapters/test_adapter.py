"""
Test Adapter Module
===================

Mock adapter for pipeline validation without network access.
Provides synthetic wine data for testing the full ingestion flow.
"""

from __future__ import annotations

import json
from typing import Any

from wine_agent.ingestion.adapters.base import (
    BaseAdapter,
    ExtractedField,
    ExtractedListing,
)


# Test wine data covering various scenarios
TEST_WINES: list[dict[str, Any]] = [
    {
        "producer": "Domaine de la Romanée-Conti",
        "wine": "La Tâche Grand Cru",
        "vintage": 2019,
        "region": "Burgundy",
        "sub_region": "Côte de Nuits",
        "appellation": "La Tâche",
        "country": "France",
        "grapes": ["Pinot Noir"],
        "color": "red",
        "style": "still",
        "abv": 13.5,
        "bottle_size_ml": 750,
        "price": 4500.00,
        "currency": "USD",
        "in_stock": True,
        "description": "Legendary Grand Cru monopole from DRC.",
    },
    {
        "producer": "Château Margaux",
        "wine": "Château Margaux",
        "vintage": 2018,
        "region": "Bordeaux",
        "sub_region": "Médoc",
        "appellation": "Margaux",
        "country": "France",
        "grapes": ["Cabernet Sauvignon", "Merlot", "Petit Verdot", "Cabernet Franc"],
        "color": "red",
        "style": "still",
        "abv": 13.0,
        "bottle_size_ml": 750,
        "price": 750.00,
        "currency": "USD",
        "in_stock": True,
        "description": "First Growth Bordeaux with exceptional aging potential.",
    },
    {
        "producer": "Krug",
        "wine": "Grande Cuvée",
        "vintage": None,  # Non-vintage
        "region": "Champagne",
        "sub_region": None,
        "appellation": "Champagne",
        "country": "France",
        "grapes": ["Chardonnay", "Pinot Noir", "Pinot Meunier"],
        "color": "white",
        "style": "sparkling",
        "abv": 12.0,
        "bottle_size_ml": 750,
        "price": 250.00,
        "currency": "USD",
        "in_stock": True,
        "description": "Prestigious multi-vintage Champagne blend.",
    },
    {
        "producer": "Giacomo Conterno",
        "wine": "Monfortino Riserva",
        "vintage": 2015,
        "region": "Piedmont",
        "sub_region": "Langhe",
        "appellation": "Barolo",
        "country": "Italy",
        "grapes": ["Nebbiolo"],
        "color": "red",
        "style": "still",
        "abv": 14.0,
        "bottle_size_ml": 750,
        "price": 950.00,
        "currency": "USD",
        "in_stock": False,
        "description": "Legendary Barolo, only produced in exceptional years.",
    },
    {
        "producer": "Vega Sicilia",
        "wine": "Único",
        "vintage": 2012,
        "region": "Ribera del Duero",
        "sub_region": None,
        "appellation": "Ribera del Duero",
        "country": "Spain",
        "grapes": ["Tempranillo", "Cabernet Sauvignon"],
        "color": "red",
        "style": "still",
        "abv": 14.5,
        "bottle_size_ml": 750,
        "price": 450.00,
        "currency": "USD",
        "in_stock": True,
        "description": "Spain's most prestigious red wine.",
    },
    {
        "producer": "Penfolds",
        "wine": "Grange",
        "vintage": 2018,
        "region": "South Australia",
        "sub_region": "Barossa Valley",
        "appellation": None,
        "country": "Australia",
        "grapes": ["Shiraz"],
        "color": "red",
        "style": "still",
        "abv": 14.5,
        "bottle_size_ml": 750,
        "price": 850.00,
        "currency": "USD",
        "in_stock": True,
        "description": "Australia's most iconic wine.",
    },
    {
        "producer": "Opus One",
        "wine": "Opus One",
        "vintage": 2019,
        "region": "Napa Valley",
        "sub_region": "Oakville",
        "appellation": "Napa Valley",
        "country": "USA",
        "grapes": ["Cabernet Sauvignon", "Merlot", "Cabernet Franc", "Petit Verdot", "Malbec"],
        "color": "red",
        "style": "still",
        "abv": 14.5,
        "bottle_size_ml": 750,
        "price": 400.00,
        "currency": "USD",
        "in_stock": True,
        "description": "Iconic Napa Valley Bordeaux blend.",
    },
    {
        "producer": "Egon Müller",
        "wine": "Scharzhofberger Riesling Spätlese",
        "vintage": 2021,
        "region": "Mosel",
        "sub_region": "Saar",
        "appellation": "Scharzhofberg",
        "country": "Germany",
        "grapes": ["Riesling"],
        "color": "white",
        "style": "still",
        "abv": 7.5,
        "bottle_size_ml": 750,
        "price": 180.00,
        "currency": "USD",
        "in_stock": True,
        "description": "World-class German Riesling from a legendary estate.",
    },
    {
        "producer": "Château d'Yquem",
        "wine": "Château d'Yquem",
        "vintage": 2017,
        "region": "Bordeaux",
        "sub_region": "Sauternes",
        "appellation": "Sauternes",
        "country": "France",
        "grapes": ["Sémillon", "Sauvignon Blanc"],
        "color": "white",
        "style": "still",
        "abv": 14.0,
        "bottle_size_ml": 375,  # Half bottle
        "price": 300.00,
        "currency": "USD",
        "in_stock": True,
        "description": "The world's greatest sweet wine.",
    },
    {
        "producer": "Taylor's",
        "wine": "Vintage Port",
        "vintage": 2017,
        "region": "Douro",
        "sub_region": None,
        "appellation": "Porto",
        "country": "Portugal",
        "grapes": ["Touriga Nacional", "Touriga Franca", "Tinta Roriz"],
        "color": "red",
        "style": "fortified",
        "abv": 20.0,
        "bottle_size_ml": 750,
        "price": 120.00,
        "currency": "USD",
        "in_stock": True,
        "description": "Classic vintage port from one of the great houses.",
    },
    {
        "producer": "Cloudy Bay",
        "wine": "Sauvignon Blanc",
        "vintage": 2023,
        "region": "Marlborough",
        "sub_region": None,
        "appellation": "Marlborough",
        "country": "New Zealand",
        "grapes": ["Sauvignon Blanc"],
        "color": "white",
        "style": "still",
        "abv": 13.0,
        "bottle_size_ml": 750,
        "price": 28.00,
        "currency": "USD",
        "in_stock": True,
        "description": "Iconic New Zealand Sauvignon Blanc.",
    },
    {
        "producer": "Antinori",
        "wine": "Tignanello",
        "vintage": 2020,
        "region": "Tuscany",
        "sub_region": "Chianti Classico",
        "appellation": "Toscana IGT",
        "country": "Italy",
        "grapes": ["Sangiovese", "Cabernet Sauvignon", "Cabernet Franc"],
        "color": "red",
        "style": "still",
        "abv": 14.0,
        "bottle_size_ml": 750,
        "price": 150.00,
        "currency": "USD",
        "in_stock": True,
        "description": "The original Super Tuscan.",
    },
    {
        "producer": "Leroy",
        "wine": "Musigny Grand Cru",
        "vintage": 2018,
        "region": "Burgundy",
        "sub_region": "Côte de Nuits",
        "appellation": "Musigny",
        "country": "France",
        "grapes": ["Pinot Noir"],
        "color": "red",
        "style": "still",
        "abv": 13.0,
        "bottle_size_ml": 750,
        "price": 8500.00,
        "currency": "USD",
        "in_stock": False,
        "description": "Rare Burgundy from biodynamic pioneer.",
    },
    {
        "producer": "Almaviva",
        "wine": "Almaviva",
        "vintage": 2020,
        "region": "Maipo Valley",
        "sub_region": "Puente Alto",
        "appellation": None,
        "country": "Chile",
        "grapes": ["Cabernet Sauvignon", "Carménère", "Cabernet Franc"],
        "color": "red",
        "style": "still",
        "abv": 14.5,
        "bottle_size_ml": 750,
        "price": 130.00,
        "currency": "USD",
        "in_stock": True,
        "description": "Chile's iconic first growth equivalent.",
    },
    {
        "producer": "Whispering Angel",
        "wine": "Côtes de Provence Rosé",
        "vintage": 2023,
        "region": "Provence",
        "sub_region": None,
        "appellation": "Côtes de Provence",
        "country": "France",
        "grapes": ["Grenache", "Cinsault", "Vermentino"],
        "color": "rosé",
        "style": "still",
        "abv": 13.0,
        "bottle_size_ml": 750,
        "price": 22.00,
        "currency": "USD",
        "in_stock": True,
        "description": "Popular premium Provençal rosé.",
    },
]


class TestAdapter(BaseAdapter):
    """
    Test adapter that returns synthetic wine data.

    Useful for:
    - Testing the full ingestion pipeline without network access
    - Validating entity resolution logic
    - Demonstrating the system to users
    """

    ADAPTER_NAME = "test"
    ADAPTER_VERSION = "1.0.0"

    BASE_URL = "https://test.wineagent.local/wines"

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(config)
        self._wines = TEST_WINES.copy()

        # Allow custom test data via config
        if config and "test_wines" in config:
            self._wines = config["test_wines"]

    def discover_urls(self, seed_urls: list[str] | None = None) -> list[str]:
        """
        Return URLs for all test wines.

        Each wine gets a URL like: https://test.wineagent.local/wines/0
        """
        return [f"{self.BASE_URL}/{i}" for i in range(len(self._wines))]

    def extract_listing(
        self,
        content: bytes,
        url: str,
        mime_type: str,
    ) -> ExtractedListing | None:
        """
        Extract wine data from test content.

        The content is expected to be JSON with a wine index.
        Falls back to parsing the URL for the index.
        """
        # Try to parse content as JSON
        wine_data = None
        try:
            data = json.loads(content)
            if isinstance(data, dict) and "index" in data:
                idx = data["index"]
                if 0 <= idx < len(self._wines):
                    wine_data = self._wines[idx]
        except (json.JSONDecodeError, KeyError):
            pass

        # Fall back to URL parsing
        if wine_data is None:
            try:
                idx = int(url.split("/")[-1])
                if 0 <= idx < len(self._wines):
                    wine_data = self._wines[idx]
            except (ValueError, IndexError):
                return None

        if wine_data is None:
            return None

        # Build extracted listing
        listing = ExtractedListing(
            url=url,
            source_name="test-wines",
            title=f"{wine_data['producer']} {wine_data['wine']} {wine_data.get('vintage', 'NV')}",
        )

        # Map wine data to extracted fields with high confidence
        # (since this is test data, we know it's accurate)
        listing.producer_name = ExtractedField(
            field_name="producer_name",
            value=wine_data["producer"],
            confidence=1.0,
            extractor_method="manual",
        )

        listing.wine_name = ExtractedField(
            field_name="wine_name",
            value=wine_data["wine"],
            confidence=1.0,
            extractor_method="manual",
        )

        if wine_data.get("vintage"):
            listing.vintage_year = ExtractedField(
                field_name="vintage_year",
                value=wine_data["vintage"],
                confidence=1.0,
                extractor_method="manual",
            )

        listing.region = ExtractedField(
            field_name="region",
            value=wine_data["region"],
            confidence=1.0,
            extractor_method="manual",
        )

        if wine_data.get("sub_region"):
            listing.sub_region = ExtractedField(
                field_name="sub_region",
                value=wine_data["sub_region"],
                confidence=1.0,
                extractor_method="manual",
            )

        if wine_data.get("appellation"):
            listing.appellation = ExtractedField(
                field_name="appellation",
                value=wine_data["appellation"],
                confidence=1.0,
                extractor_method="manual",
            )

        listing.country = ExtractedField(
            field_name="country",
            value=wine_data["country"],
            confidence=1.0,
            extractor_method="manual",
        )

        listing.grapes = ExtractedField(
            field_name="grapes",
            value=wine_data["grapes"],
            confidence=1.0,
            extractor_method="manual",
        )

        listing.color = ExtractedField(
            field_name="color",
            value=wine_data["color"],
            confidence=1.0,
            extractor_method="manual",
        )

        listing.style = ExtractedField(
            field_name="style",
            value=wine_data["style"],
            confidence=1.0,
            extractor_method="manual",
        )

        listing.abv = ExtractedField(
            field_name="abv",
            value=wine_data["abv"],
            confidence=1.0,
            extractor_method="manual",
        )

        listing.bottle_size_ml = ExtractedField(
            field_name="bottle_size_ml",
            value=wine_data["bottle_size_ml"],
            confidence=1.0,
            extractor_method="manual",
        )

        listing.price = ExtractedField(
            field_name="price",
            value=wine_data["price"],
            confidence=1.0,
            extractor_method="manual",
        )

        listing.currency = ExtractedField(
            field_name="currency",
            value=wine_data["currency"],
            confidence=1.0,
            extractor_method="manual",
        )

        listing.in_stock = ExtractedField(
            field_name="in_stock",
            value=wine_data["in_stock"],
            confidence=1.0,
            extractor_method="manual",
        )

        listing.description = ExtractedField(
            field_name="description",
            value=wine_data["description"],
            confidence=1.0,
            extractor_method="manual",
        )

        return listing

    def get_test_content(self, index: int) -> bytes:
        """
        Generate test content for a wine index.

        This is used by the test crawler to simulate fetching.
        """
        return json.dumps({"index": index}).encode("utf-8")
