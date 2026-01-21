"""End-to-end tests for the ingestion pipeline."""

import tempfile
from pathlib import Path

import pytest
import yaml

from wine_agent.ingestion.adapters import get_adapter
from wine_agent.ingestion.adapters.test_adapter import TEST_WINES, TestAdapter
from wine_agent.ingestion.normalizer import Normalizer
from wine_agent.ingestion.registry import SourceRegistry
from wine_agent.ingestion.storage import LocalFileStorage


class TestIngestionPipeline:
    """End-to-end tests for the ingestion pipeline."""

    @pytest.fixture
    def config_file(self) -> str:
        """Create a temporary config file."""
        config = {
            "global": {
                "default_rate_limit": {
                    "requests_per_second": 10.0,
                    "burst_limit": 20,
                },
                "user_agent": "TestAgent/1.0",
                "snapshot_storage_path": "/tmp/test_snapshots",
            },
            "entity_resolution": {
                "thresholds": {
                    "auto_merge": 0.90,
                    "review_queue": 0.70,
                },
            },
            "sources": [
                {
                    "name": "test-wines",
                    "domain": "test.wineagent.local",
                    "adapter": "test",
                    "enabled": True,
                    "description": "Test source",
                    "rate_limit": {
                        "requests_per_second": 10.0,
                        "burst_limit": 20,
                    },
                }
            ],
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config, f)
            return f.name

    def test_full_pipeline_discovery_to_normalization(self, config_file: str) -> None:
        """Test the full pipeline from URL discovery to normalization."""
        # 1. Load configuration
        registry = SourceRegistry()
        registry.load_config(config_file)

        source = registry.get_source("test-wines")
        assert source is not None

        # 2. Get adapter
        adapter = get_adapter(source.adapter)
        assert adapter is not None

        # 3. Discover URLs
        urls = adapter.discover_urls()
        assert len(urls) == len(TEST_WINES)

        # 4. Process each URL
        normalizer = Normalizer()
        processed = []

        for url in urls[:5]:  # Process first 5
            # Get test content
            idx = int(url.split("/")[-1])
            content = adapter.get_test_content(idx)

            # Extract listing
            extracted = adapter.extract_listing(content, url, "application/json")
            assert extracted is not None

            # Validate
            errors = adapter.validate_listing(extracted)
            assert errors == [], f"Validation errors: {errors}"

            # Normalize
            normalized = normalizer.normalize_listing(extracted)
            processed.append(normalized)

            # Verify normalization
            assert normalized.producer_name is not None
            assert normalized.wine_name is not None

        assert len(processed) == 5

        # Verify first wine (DRC La Tâche)
        first = processed[0]
        assert first.producer_name == "Domaine de la Romanée-Conti"
        assert first.wine_name == "La Tâche Grand Cru"
        assert first.vintage_year == 2019
        assert first.region == "Bourgogne"  # Normalized from "Burgundy"
        assert "Pinot Noir" in first.grapes

        # Clean up
        Path(config_file).unlink()

    def test_pipeline_with_storage(self) -> None:
        """Test the pipeline with snapshot storage."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Initialize storage
            storage = LocalFileStorage(tmpdir)

            # Get adapter
            adapter = TestAdapter()
            urls = adapter.discover_urls()[:3]

            # Process and store
            from uuid import uuid4

            source_id = uuid4()
            snapshots = []

            for url in urls:
                idx = int(url.split("/")[-1])
                content = adapter.get_test_content(idx)

                # Store snapshot
                from wine_agent.ingestion.crawler import Crawler

                content_hash = Crawler.compute_hash(content)
                metadata = storage.save_snapshot(
                    content=content,
                    source_id=source_id,
                    url=url,
                    content_hash=content_hash,
                    mime_type="application/json",
                )
                snapshots.append(metadata)

            # Verify storage
            assert len(snapshots) == 3
            stats = storage.get_storage_stats()
            assert stats["total_snapshots"] == 3

            # Verify retrieval
            for snapshot in snapshots:
                retrieved = storage.get_snapshot(snapshot.snapshot_id)
                assert retrieved is not None

    def test_pipeline_grape_normalization(self) -> None:
        """Test that grapes are properly normalized through the pipeline."""
        adapter = TestAdapter()
        normalizer = Normalizer()

        # Process wine with grape aliases
        content = adapter.get_test_content(0)  # DRC - Pinot Noir
        extracted = adapter.extract_listing(
            content,
            "https://test.wineagent.local/wines/0",
            "application/json",
        )
        normalized = normalizer.normalize_listing(extracted)

        assert "Pinot Noir" in normalized.grapes

        # Process wine with multiple grapes
        content = adapter.get_test_content(1)  # Margaux - Cab, Merlot, etc.
        extracted = adapter.extract_listing(
            content,
            "https://test.wineagent.local/wines/1",
            "application/json",
        )
        normalized = normalizer.normalize_listing(extracted)

        assert "Cabernet Sauvignon" in normalized.grapes
        assert "Merlot" in normalized.grapes

    def test_pipeline_region_normalization(self) -> None:
        """Test that regions are properly normalized through the pipeline."""
        adapter = TestAdapter()
        normalizer = Normalizer()

        # Test wines with various regions
        test_cases = [
            (0, "Bourgogne"),  # Burgundy -> Bourgogne
            (1, "Bordeaux"),
            (2, "Champagne"),
            (5, "South Australia"),  # Region stays as-is, Barossa Valley is in sub_region
        ]

        for idx, expected_region in test_cases:
            content = adapter.get_test_content(idx)
            extracted = adapter.extract_listing(
                content,
                f"https://test.wineagent.local/wines/{idx}",
                "application/json",
            )
            normalized = normalizer.normalize_listing(extracted)

            assert normalized.region == expected_region, (
                f"Wine {idx}: expected {expected_region}, got {normalized.region}"
            )

    def test_pipeline_nv_wine(self) -> None:
        """Test pipeline handles non-vintage wines correctly."""
        adapter = TestAdapter()
        normalizer = Normalizer()

        # Krug Grande Cuvée is NV (index 2)
        content = adapter.get_test_content(2)
        extracted = adapter.extract_listing(
            content,
            "https://test.wineagent.local/wines/2",
            "application/json",
        )
        normalized = normalizer.normalize_listing(extracted)

        assert normalized.vintage_year is None
        assert normalized.producer_name == "Krug"
        assert normalized.style == "sparkling"

    def test_pipeline_fortified_wine(self) -> None:
        """Test pipeline handles fortified wines correctly."""
        adapter = TestAdapter()
        normalizer = Normalizer()

        # Taylor's Port is index 9
        content = adapter.get_test_content(9)
        extracted = adapter.extract_listing(
            content,
            "https://test.wineagent.local/wines/9",
            "application/json",
        )
        normalized = normalizer.normalize_listing(extracted)

        assert normalized.style == "fortified"
        assert normalized.abv == 20.0

    def test_pipeline_all_test_wines(self) -> None:
        """Test that all test wines can be processed without errors."""
        adapter = TestAdapter()
        normalizer = Normalizer()

        urls = adapter.discover_urls()

        for url in urls:
            idx = int(url.split("/")[-1])
            content = adapter.get_test_content(idx)
            extracted = adapter.extract_listing(content, url, "application/json")

            assert extracted is not None, f"Failed to extract wine at index {idx}"

            errors = adapter.validate_listing(extracted)
            assert errors == [], f"Validation errors for wine {idx}: {errors}"

            normalized = normalizer.normalize_listing(extracted)
            assert normalized.source_name == "test-wines"
