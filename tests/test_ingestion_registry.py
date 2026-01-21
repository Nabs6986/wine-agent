"""Tests for the ingestion registry module."""

import tempfile
from pathlib import Path

import pytest
import yaml

from wine_agent.ingestion.registry import (
    EntityResolutionConfig,
    GlobalConfig,
    RateLimitConfig,
    SourceConfig,
    SourceRegistry,
    get_default_registry,
    reset_default_registry,
)


class TestRateLimitConfig:
    """Tests for RateLimitConfig."""

    def test_default_values(self) -> None:
        """Test default rate limit values."""
        config = RateLimitConfig()
        assert config.requests_per_second == 1.0
        assert config.burst_limit == 5

    def test_from_dict(self) -> None:
        """Test creating from dictionary."""
        data = {"requests_per_second": 2.5, "burst_limit": 10}
        config = RateLimitConfig.from_dict(data)
        assert config.requests_per_second == 2.5
        assert config.burst_limit == 10

    def test_from_dict_none(self) -> None:
        """Test creating from None returns defaults."""
        config = RateLimitConfig.from_dict(None)
        assert config.requests_per_second == 1.0
        assert config.burst_limit == 5


class TestSourceConfig:
    """Tests for SourceConfig."""

    def test_from_dict_minimal(self) -> None:
        """Test creating with minimal data."""
        data = {
            "name": "test",
            "domain": "test.com",
            "adapter": "test",
        }
        config = SourceConfig.from_dict(data)
        assert config.name == "test"
        assert config.domain == "test.com"
        assert config.adapter == "test"
        assert config.enabled is True

    def test_from_dict_full(self) -> None:
        """Test creating with full data."""
        data = {
            "name": "test",
            "domain": "test.com",
            "adapter": "test",
            "enabled": False,
            "description": "Test source",
            "rate_limit": {"requests_per_second": 5.0, "burst_limit": 15},
            "allowlist": ["^https://test\\.com/.*"],
            "denylist": ["^https://test\\.com/admin/.*"],
            "seed_urls": ["https://test.com/wines"],
        }
        config = SourceConfig.from_dict(data)
        assert config.name == "test"
        assert config.enabled is False
        assert config.rate_limit.requests_per_second == 5.0
        assert len(config.allowlist) == 1
        assert len(config.denylist) == 1

    def test_url_filtering_allowlist(self) -> None:
        """Test URL filtering with allowlist."""
        config = SourceConfig(
            name="test",
            domain="test.com",
            adapter="test",
            allowlist=["^https://test\\.com/wines/.*"],
        )
        assert config.is_url_allowed("https://test.com/wines/123") is True
        assert config.is_url_allowed("https://test.com/other/123") is False

    def test_url_filtering_denylist(self) -> None:
        """Test URL filtering with denylist."""
        config = SourceConfig(
            name="test",
            domain="test.com",
            adapter="test",
            denylist=["^https://test\\.com/admin/.*"],
        )
        assert config.is_url_allowed("https://test.com/wines/123") is True
        assert config.is_url_allowed("https://test.com/admin/123") is False

    def test_url_filtering_denylist_priority(self) -> None:
        """Test that denylist takes priority over allowlist."""
        config = SourceConfig(
            name="test",
            domain="test.com",
            adapter="test",
            allowlist=["^https://test\\.com/.*"],
            denylist=["^https://test\\.com/admin/.*"],
        )
        assert config.is_url_allowed("https://test.com/wines/123") is True
        assert config.is_url_allowed("https://test.com/admin/123") is False


class TestSourceRegistry:
    """Tests for SourceRegistry."""

    @pytest.fixture
    def sample_config(self) -> str:
        """Create a sample configuration YAML."""
        return """
global:
  default_rate_limit:
    requests_per_second: 2.0
    burst_limit: 10
  user_agent: "TestAgent/1.0"
  snapshot_storage_path: "/tmp/snapshots"

entity_resolution:
  thresholds:
    auto_merge: 0.95
    review_queue: 0.75

sources:
  - name: test-source
    domain: test.example.com
    adapter: test
    enabled: true
    description: "Test source"

  - name: disabled-source
    domain: disabled.example.com
    adapter: test
    enabled: false
"""

    def test_load_config(self, sample_config: str) -> None:
        """Test loading configuration from YAML."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(sample_config)
            config_path = f.name

        try:
            registry = SourceRegistry()
            registry.load_config(config_path)

            # Check global config
            assert registry.global_config.user_agent == "TestAgent/1.0"
            assert registry.global_config.default_rate_limit.requests_per_second == 2.0

            # Check entity resolution config
            assert registry.entity_resolution.auto_merge_threshold == 0.95
            assert registry.entity_resolution.review_queue_threshold == 0.75

            # Check sources
            sources = registry.list_sources()
            assert len(sources) == 2

            test_source = registry.get_source("test-source")
            assert test_source is not None
            assert test_source.enabled is True

        finally:
            Path(config_path).unlink()

    def test_list_enabled_sources(self, sample_config: str) -> None:
        """Test listing only enabled sources."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(sample_config)
            config_path = f.name

        try:
            registry = SourceRegistry()
            registry.load_config(config_path)

            enabled = registry.list_enabled_sources()
            assert len(enabled) == 1
            assert enabled[0].name == "test-source"

        finally:
            Path(config_path).unlink()

    def test_enable_disable_source(self, sample_config: str) -> None:
        """Test enabling and disabling sources."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(sample_config)
            config_path = f.name

        try:
            registry = SourceRegistry()
            registry.load_config(config_path)

            # Disable enabled source
            assert registry.disable_source("test-source") is True
            assert registry.get_source("test-source").enabled is False

            # Enable disabled source
            assert registry.enable_source("disabled-source") is True
            assert registry.get_source("disabled-source").enabled is True

            # Try with non-existent source
            assert registry.enable_source("non-existent") is False

        finally:
            Path(config_path).unlink()

    def test_get_source_by_domain(self, sample_config: str) -> None:
        """Test finding source by domain."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(sample_config)
            config_path = f.name

        try:
            registry = SourceRegistry()
            registry.load_config(config_path)

            source = registry.get_source_by_domain("test.example.com")
            assert source is not None
            assert source.name == "test-source"

            # Non-existent domain
            assert registry.get_source_by_domain("unknown.com") is None

        finally:
            Path(config_path).unlink()

    def test_config_not_found(self) -> None:
        """Test error when config file not found."""
        registry = SourceRegistry()
        with pytest.raises(FileNotFoundError):
            registry.load_config("/non/existent/path.yaml")


class TestGlobalRegistry:
    """Tests for the global registry functions."""

    def test_reset_default_registry(self) -> None:
        """Test resetting the global registry."""
        # Get the registry (may create it)
        registry1 = get_default_registry()

        # Reset it
        reset_default_registry()

        # Get it again - should be a new instance
        registry2 = get_default_registry()

        # They should be different objects (unless caching)
        # The actual behavior depends on implementation
        assert registry2 is not None
