"""
Wine Agent Ingestion Framework
==============================

This package provides the complete ingestion pipeline for crawling wine data
from external sources and resolving them to canonical entities.

Pipeline Stages:
1. Discovery - Adapters find URLs to crawl from a source
2. Fetch - Crawler respects robots.txt, rate limits, fetches content
3. Parse - Adapters extract structured data from HTML/JSON
4. Normalize - Clean up region names, grape varieties, ABV, bottle sizes
5. Resolve - Match listings to canonical entities with confidence scoring
6. Persist - Save listings, matches, and create/update canonical entities
7. Index - Update Meilisearch for search
"""

from wine_agent.ingestion.registry import (
    SourceRegistry,
    SourceConfig,
    RateLimitConfig,
    get_default_registry,
)
from wine_agent.ingestion.crawler import (
    Crawler,
    FetchResult,
    TokenBucket,
    RobotsChecker,
)
from wine_agent.ingestion.storage import (
    SnapshotStorage,
    LocalFileStorage,
    SnapshotMetadata,
)
from wine_agent.ingestion.normalizer import (
    Normalizer,
    NormalizedListing,
)
from wine_agent.ingestion.resolver import (
    EntityResolver,
    ResolutionResult,
    MatchAction,
    MatchCandidate,
)
from wine_agent.ingestion.jobs import (
    ingest_source,
    enqueue_ingestion,
    get_job_status,
    JobResult,
    JobStatus,
)

__all__ = [
    # Registry
    "SourceRegistry",
    "SourceConfig",
    "RateLimitConfig",
    "get_default_registry",
    # Crawler
    "Crawler",
    "FetchResult",
    "TokenBucket",
    "RobotsChecker",
    # Storage
    "SnapshotStorage",
    "LocalFileStorage",
    "SnapshotMetadata",
    # Normalizer
    "Normalizer",
    "NormalizedListing",
    # Resolver
    "EntityResolver",
    "ResolutionResult",
    "MatchAction",
    "MatchCandidate",
    # Jobs
    "ingest_source",
    "enqueue_ingestion",
    "get_job_status",
    "JobResult",
    "JobStatus",
]
