"""
Adapter Registry Module
=======================

Central registry for source-specific adapters.
Provides factory functions for creating adapters by name.
"""

from __future__ import annotations

from typing import Any, Type

from wine_agent.ingestion.adapters.base import BaseAdapter, ExtractedField, ExtractedListing
from wine_agent.ingestion.adapters.test_adapter import TestAdapter


# Registry mapping adapter names to their classes
ADAPTER_REGISTRY: dict[str, Type[BaseAdapter]] = {
    "test": TestAdapter,
}


def get_adapter(
    adapter_type: str,
    config: dict[str, Any] | None = None,
) -> BaseAdapter | None:
    """
    Get an adapter instance by type name.

    Args:
        adapter_type: Name of the adapter (e.g., "test")
        config: Optional custom configuration

    Returns:
        Adapter instance, or None if type not found
    """
    adapter_class = ADAPTER_REGISTRY.get(adapter_type)
    if adapter_class is None:
        return None
    return adapter_class(config)


def register_adapter(name: str, adapter_class: Type[BaseAdapter]) -> None:
    """
    Register a new adapter type.

    Args:
        name: Name to register the adapter under
        adapter_class: Adapter class (must inherit from BaseAdapter)
    """
    if not issubclass(adapter_class, BaseAdapter):
        raise TypeError(f"{adapter_class} must inherit from BaseAdapter")
    ADAPTER_REGISTRY[name] = adapter_class


def list_adapters() -> list[str]:
    """
    List all registered adapter names.

    Returns:
        List of adapter type names
    """
    return list(ADAPTER_REGISTRY.keys())


def get_adapter_info(adapter_type: str) -> dict[str, str] | None:
    """
    Get information about an adapter type.

    Args:
        adapter_type: Name of the adapter

    Returns:
        Dict with adapter info, or None if not found
    """
    adapter_class = ADAPTER_REGISTRY.get(adapter_type)
    if adapter_class is None:
        return None

    return {
        "name": adapter_class.ADAPTER_NAME,
        "version": adapter_class.ADAPTER_VERSION,
        "class": adapter_class.__name__,
    }


__all__ = [
    # Registry functions
    "get_adapter",
    "register_adapter",
    "list_adapters",
    "get_adapter_info",
    "ADAPTER_REGISTRY",
    # Base classes
    "BaseAdapter",
    "ExtractedField",
    "ExtractedListing",
    # Concrete adapters
    "TestAdapter",
]
