"""
Source Registry Module
======================

Manages source configurations loaded from YAML files. Sources define
which websites/APIs can be crawled and their associated settings.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class RateLimitConfig:
    """Rate limiting configuration for a source."""

    requests_per_second: float = 1.0
    burst_limit: int = 5

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> RateLimitConfig:
        """Create from dictionary, using defaults for missing values."""
        if data is None:
            return cls()
        return cls(
            requests_per_second=float(data.get("requests_per_second", 1.0)),
            burst_limit=int(data.get("burst_limit", 5)),
        )


@dataclass
class SourceConfig:
    """Configuration for a single ingestion source."""

    name: str
    domain: str
    adapter: str
    enabled: bool = True
    description: str = ""
    rate_limit: RateLimitConfig = field(default_factory=RateLimitConfig)
    allowlist: list[str] = field(default_factory=list)
    denylist: list[str] = field(default_factory=list)
    seed_urls: list[str] = field(default_factory=list)
    custom_config: dict[str, Any] = field(default_factory=dict)

    # Compiled regex patterns (populated lazily)
    _allowlist_patterns: list[re.Pattern[str]] | None = field(
        default=None, repr=False, compare=False
    )
    _denylist_patterns: list[re.Pattern[str]] | None = field(
        default=None, repr=False, compare=False
    )

    @classmethod
    def from_dict(
        cls, data: dict[str, Any], default_rate_limit: RateLimitConfig | None = None
    ) -> SourceConfig:
        """Create from dictionary."""
        rate_limit_data = data.get("rate_limit")
        if rate_limit_data:
            rate_limit = RateLimitConfig.from_dict(rate_limit_data)
        elif default_rate_limit:
            rate_limit = default_rate_limit
        else:
            rate_limit = RateLimitConfig()

        return cls(
            name=data["name"],
            domain=data["domain"],
            adapter=data["adapter"],
            enabled=data.get("enabled", True),
            description=data.get("description", ""),
            rate_limit=rate_limit,
            allowlist=data.get("allowlist", []),
            denylist=data.get("denylist", []),
            seed_urls=data.get("seed_urls", []),
            custom_config=data.get("custom_config", {}),
        )

    def _compile_patterns(self) -> None:
        """Compile regex patterns for URL filtering."""
        if self._allowlist_patterns is None:
            self._allowlist_patterns = [re.compile(p) for p in self.allowlist]
        if self._denylist_patterns is None:
            self._denylist_patterns = [re.compile(p) for p in self.denylist]

    def is_url_allowed(self, url: str) -> bool:
        """
        Check if a URL is allowed for this source.

        Rules:
        1. If URL matches any denylist pattern, it's denied
        2. If allowlist is empty, URL is allowed
        3. If allowlist is not empty, URL must match at least one pattern
        """
        self._compile_patterns()

        # Check denylist first
        for pattern in self._denylist_patterns or []:
            if pattern.match(url):
                return False

        # If no allowlist, allow everything not denied
        if not self._allowlist_patterns:
            return True

        # Check allowlist
        for pattern in self._allowlist_patterns or []:
            if pattern.match(url):
                return True

        return False


@dataclass
class EntityResolutionConfig:
    """Configuration for entity resolution thresholds."""

    auto_merge_threshold: float = 0.90
    review_queue_threshold: float = 0.70

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> EntityResolutionConfig:
        """Create from dictionary."""
        if data is None:
            return cls()
        thresholds = data.get("thresholds", {})
        return cls(
            auto_merge_threshold=float(thresholds.get("auto_merge", 0.90)),
            review_queue_threshold=float(thresholds.get("review_queue", 0.70)),
        )


@dataclass
class GlobalConfig:
    """Global configuration settings."""

    default_rate_limit: RateLimitConfig = field(default_factory=RateLimitConfig)
    user_agent: str = "WineAgent/0.1"
    snapshot_storage_path: str = "~/.wine_agent/snapshots"
    request_timeout: int = 30
    max_retries: int = 3

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> GlobalConfig:
        """Create from dictionary."""
        if data is None:
            return cls()
        return cls(
            default_rate_limit=RateLimitConfig.from_dict(
                data.get("default_rate_limit")
            ),
            user_agent=data.get("user_agent", "WineAgent/0.1"),
            snapshot_storage_path=data.get(
                "snapshot_storage_path", "~/.wine_agent/snapshots"
            ),
            request_timeout=int(data.get("request_timeout", 30)),
            max_retries=int(data.get("max_retries", 3)),
        )


class SourceRegistry:
    """
    Registry for managing ingestion source configurations.

    Loads source definitions from a YAML file and provides methods
    to query and manage them.
    """

    def __init__(self) -> None:
        self._sources: dict[str, SourceConfig] = {}
        self._global_config: GlobalConfig = GlobalConfig()
        self._entity_resolution: EntityResolutionConfig = EntityResolutionConfig()
        self._config_path: Path | None = None

    @property
    def global_config(self) -> GlobalConfig:
        """Get global configuration."""
        return self._global_config

    @property
    def entity_resolution(self) -> EntityResolutionConfig:
        """Get entity resolution configuration."""
        return self._entity_resolution

    def load_config(self, config_path: Path | str) -> None:
        """
        Load configuration from a YAML file.

        Args:
            config_path: Path to the sources.yaml file
        """
        config_path = Path(config_path).expanduser().resolve()
        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")

        with open(config_path) as f:
            data = yaml.safe_load(f)

        self._config_path = config_path
        self._global_config = GlobalConfig.from_dict(data.get("global"))
        self._entity_resolution = EntityResolutionConfig.from_dict(
            data.get("entity_resolution")
        )

        # Load sources
        self._sources.clear()
        for source_data in data.get("sources", []):
            source = SourceConfig.from_dict(
                source_data, self._global_config.default_rate_limit
            )
            self._sources[source.name] = source

    def get_source(self, name: str) -> SourceConfig | None:
        """
        Get a source configuration by name.

        Args:
            name: Source name

        Returns:
            SourceConfig if found, None otherwise
        """
        return self._sources.get(name)

    def list_sources(self) -> list[SourceConfig]:
        """
        Get all registered sources.

        Returns:
            List of all source configurations
        """
        return list(self._sources.values())

    def list_enabled_sources(self) -> list[SourceConfig]:
        """
        Get all enabled sources.

        Returns:
            List of enabled source configurations
        """
        return [s for s in self._sources.values() if s.enabled]

    def enable_source(self, name: str) -> bool:
        """
        Enable a source.

        Args:
            name: Source name

        Returns:
            True if source was found and enabled, False otherwise
        """
        source = self._sources.get(name)
        if source is None:
            return False
        source.enabled = True
        return True

    def disable_source(self, name: str) -> bool:
        """
        Disable a source.

        Args:
            name: Source name

        Returns:
            True if source was found and disabled, False otherwise
        """
        source = self._sources.get(name)
        if source is None:
            return False
        source.enabled = False
        return True

    def get_source_by_domain(self, domain: str) -> SourceConfig | None:
        """
        Find a source by its domain.

        Args:
            domain: Domain name (e.g., "example.com")

        Returns:
            SourceConfig if found, None otherwise
        """
        for source in self._sources.values():
            if source.domain == domain:
                return source
        return None


# Global registry instance
_default_registry: SourceRegistry | None = None


def get_default_registry() -> SourceRegistry:
    """
    Get the default source registry instance.

    Loads configuration from the path specified in SOURCES_CONFIG_PATH
    environment variable, or falls back to config/sources.yaml.

    Returns:
        The global SourceRegistry instance
    """
    global _default_registry

    if _default_registry is None:
        _default_registry = SourceRegistry()

        # Determine config path
        config_path = os.environ.get("SOURCES_CONFIG_PATH")
        if config_path:
            path = Path(config_path)
        else:
            # Default to config/sources.yaml relative to project root
            # Try to find it relative to this file
            module_dir = Path(__file__).parent
            project_root = module_dir.parent.parent
            path = project_root / "config" / "sources.yaml"

        if path.exists():
            _default_registry.load_config(path)

    return _default_registry


def reset_default_registry() -> None:
    """Reset the default registry (useful for testing)."""
    global _default_registry
    _default_registry = None
