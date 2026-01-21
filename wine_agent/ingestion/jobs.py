"""
Background Jobs Module
======================

Defines arq tasks for asynchronous ingestion processing.
Uses Redis as the job queue backend.
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

from wine_agent.db.engine import get_session
from wine_agent.db.models_canonical import ListingDB, ListingMatchDB, SnapshotDB, SourceDB
from wine_agent.ingestion.adapters import get_adapter
from wine_agent.ingestion.adapters.test_adapter import TestAdapter
from wine_agent.ingestion.crawler import Crawler
from wine_agent.ingestion.normalizer import Normalizer
from wine_agent.ingestion.registry import get_default_registry
from wine_agent.ingestion.resolver import EntityResolver, MatchAction, create_entities_from_listing
from wine_agent.ingestion.storage import get_default_storage

logger = logging.getLogger(__name__)


class JobStatus(str, Enum):
    """Status of an ingestion job."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class JobResult:
    """Result of an ingestion job."""

    job_id: str
    source_name: str
    status: JobStatus
    started_at: datetime | None = None
    completed_at: datetime | None = None
    urls_discovered: int = 0
    urls_fetched: int = 0
    listings_created: int = 0
    entities_created: int = 0
    entities_matched: int = 0
    review_queue_count: int = 0
    errors: list[str] = field(default_factory=list)
    duration_seconds: float | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "job_id": self.job_id,
            "source_name": self.source_name,
            "status": self.status.value,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "urls_discovered": self.urls_discovered,
            "urls_fetched": self.urls_fetched,
            "listings_created": self.listings_created,
            "entities_created": self.entities_created,
            "entities_matched": self.entities_matched,
            "review_queue_count": self.review_queue_count,
            "errors": self.errors,
            "duration_seconds": self.duration_seconds,
        }


def get_redis_settings() -> RedisSettings:
    """Get Redis connection settings from environment."""
    return RedisSettings(
        host=os.environ.get("REDIS_HOST", "localhost"),
        port=int(os.environ.get("REDIS_PORT", "6379")),
        database=int(os.environ.get("REDIS_DB", "0")),
    )


async def ingest_source(
    ctx: dict[str, Any],
    source_name: str,
    max_urls: int | None = None,
) -> dict[str, Any]:
    """
    Main ingestion task.

    Orchestrates the full ingestion pipeline:
    1. Load source configuration
    2. Discover URLs via adapter
    3. Fetch content with crawler
    4. Extract listings with adapter
    5. Normalize data
    6. Resolve to canonical entities
    7. Persist results

    Args:
        ctx: arq context (contains Redis connection)
        source_name: Name of the source to ingest
        max_urls: Optional limit on URLs to process

    Returns:
        JobResult as dictionary
    """
    job_id = ctx.get("job_id", str(uuid4()))
    result = JobResult(
        job_id=job_id,
        source_name=source_name,
        status=JobStatus.RUNNING,
        started_at=datetime.utcnow(),
    )

    try:
        # Load source configuration
        registry = get_default_registry()
        source_config = registry.get_source(source_name)

        if source_config is None:
            result.status = JobStatus.FAILED
            result.errors.append(f"Source '{source_name}' not found")
            return result.to_dict()

        if not source_config.enabled:
            result.status = JobStatus.FAILED
            result.errors.append(f"Source '{source_name}' is disabled")
            return result.to_dict()

        # Get adapter
        adapter = get_adapter(source_config.adapter, source_config.custom_config)
        if adapter is None:
            result.status = JobStatus.FAILED
            result.errors.append(f"Adapter '{source_config.adapter}' not found")
            return result.to_dict()

        # Initialize components
        global_config = registry.global_config
        crawler = Crawler(
            user_agent=global_config.user_agent,
            timeout=global_config.request_timeout,
            max_retries=global_config.max_retries,
        )
        storage = get_default_storage()
        normalizer = Normalizer()

        # Discover URLs
        logger.info(f"Discovering URLs for source '{source_name}'...")
        urls = adapter.discover_urls(source_config.seed_urls or None)
        result.urls_discovered = len(urls)

        if max_urls:
            urls = urls[:max_urls]

        logger.info(f"Found {len(urls)} URLs to process")

        # Get or create source in database
        with get_session() as session:
            source_db = session.query(SourceDB).filter(SourceDB.domain == source_config.domain).first()
            if source_db is None:
                source_db = SourceDB(
                    id=str(uuid4()),
                    domain=source_config.domain,
                    adapter_type=source_config.adapter,
                    enabled=source_config.enabled,
                )
                session.add(source_db)
                session.commit()
            source_id = source_db.id

            # Initialize resolver
            resolver = EntityResolver.from_config(session, registry.entity_resolution)

            # Process URLs
            for url in urls:
                try:
                    snapshot_id = None
                    # For test adapter, generate synthetic content
                    if isinstance(adapter, TestAdapter):
                        idx = int(url.split("/")[-1])
                        content = adapter.get_test_content(idx)
                        mime_type = "application/json"
                        # Create a placeholder snapshot for test adapter
                        from wine_agent.ingestion.crawler import Crawler
                        test_hash = Crawler.compute_hash(content)
                        snapshot_db = SnapshotDB(
                            id=str(uuid4()),
                            source_id=source_id,
                            url=url,
                            content_hash=test_hash,
                            mime_type=mime_type,
                            file_path="",
                        )
                        session.add(snapshot_db)
                        snapshot_id = snapshot_db.id
                    else:
                        # Fetch content
                        fetch_result = await crawler.fetch(url, source_config)

                        if not fetch_result.success:
                            result.errors.append(f"Failed to fetch {url}: {fetch_result.error}")
                            continue

                        content = fetch_result.content
                        mime_type = fetch_result.mime_type

                        # Store snapshot
                        snapshot_meta = storage.save_snapshot(
                            content=content,
                            source_id=source_id,
                            url=url,
                            content_hash=fetch_result.content_hash,
                            mime_type=mime_type,
                        )

                        # Create snapshot record in database
                        snapshot_db = SnapshotDB(
                            id=str(snapshot_meta.snapshot_id),
                            source_id=source_id,
                            url=url,
                            content_hash=snapshot_meta.content_hash,
                            mime_type=mime_type,
                            file_path=snapshot_meta.file_path,
                        )
                        session.add(snapshot_db)
                        snapshot_id = snapshot_db.id

                    result.urls_fetched += 1

                    # Extract listing
                    extracted = adapter.extract_listing(content, url, mime_type)
                    if extracted is None:
                        result.errors.append(f"Failed to extract listing from {url}")
                        continue

                    # Validate
                    validation_errors = adapter.validate_listing(extracted)
                    if validation_errors:
                        result.errors.extend([f"{url}: {e}" for e in validation_errors])

                    # Normalize
                    normalized = normalizer.normalize_listing(extracted)

                    # Resolve to entities
                    resolution = resolver.resolve(normalized)

                    # Create entities if needed
                    entities = create_entities_from_listing(session, normalized, resolution)

                    # Count results
                    if resolution.action == MatchAction.AUTO_MERGE:
                        result.entities_matched += 1
                    elif resolution.action == MatchAction.REVIEW_QUEUE:
                        result.review_queue_count += 1

                    if resolution.create_producer:
                        result.entities_created += 1
                    if resolution.create_wine:
                        result.entities_created += 1
                    if resolution.create_vintage:
                        result.entities_created += 1

                    # Create listing record
                    import json
                    listing_db = ListingDB(
                        id=str(resolution.listing_id),
                        source_id=source_id,
                        snapshot_id=snapshot_id,
                        url=url,
                        title=extracted.title or "",
                        price=normalized.price,
                        currency=normalized.currency or "USD",
                        parsed_fields_json=json.dumps(extracted.to_dict()),
                    )
                    session.add(listing_db)
                    result.listings_created += 1

                    # Create listing match records
                    if resolution.producer_match:
                        match_db = ListingMatchDB(
                            id=str(uuid4()),
                            listing_id=listing_db.id,
                            entity_type="producer",
                            entity_id=str(resolution.producer_match.entity_id),
                            confidence=resolution.producer_match.confidence,
                            decision="auto" if resolution.action == MatchAction.AUTO_MERGE else "pending",
                        )
                        session.add(match_db)
                    if resolution.wine_match:
                        match_db = ListingMatchDB(
                            id=str(uuid4()),
                            listing_id=listing_db.id,
                            entity_type="wine",
                            entity_id=str(resolution.wine_match.entity_id),
                            confidence=resolution.wine_match.confidence,
                            decision="auto" if resolution.action == MatchAction.AUTO_MERGE else "pending",
                        )
                        session.add(match_db)
                    if resolution.vintage_match:
                        match_db = ListingMatchDB(
                            id=str(uuid4()),
                            listing_id=listing_db.id,
                            entity_type="vintage",
                            entity_id=str(resolution.vintage_match.entity_id),
                            confidence=resolution.vintage_match.confidence,
                            decision="auto" if resolution.action == MatchAction.AUTO_MERGE else "pending",
                        )
                        session.add(match_db)

                except Exception as e:
                    logger.exception(f"Error processing {url}")
                    result.errors.append(f"{url}: {str(e)}")

            # Commit all changes
            session.commit()

        result.status = JobStatus.COMPLETED

    except Exception as e:
        logger.exception(f"Ingestion job failed: {e}")
        result.status = JobStatus.FAILED
        result.errors.append(str(e))

    finally:
        result.completed_at = datetime.utcnow()
        if result.started_at and result.completed_at:
            result.duration_seconds = (result.completed_at - result.started_at).total_seconds()

    return result.to_dict()


async def ingest_source_sync(
    source_name: str,
    max_urls: int | None = None,
) -> JobResult:
    """
    Run ingestion synchronously (without arq).

    Useful for CLI commands with --sync flag.

    Args:
        source_name: Name of the source to ingest
        max_urls: Optional limit on URLs to process

    Returns:
        JobResult
    """
    ctx: dict[str, Any] = {"job_id": str(uuid4())}
    result_dict = await ingest_source(ctx, source_name, max_urls)

    return JobResult(
        job_id=result_dict["job_id"],
        source_name=result_dict["source_name"],
        status=JobStatus(result_dict["status"]),
        started_at=datetime.fromisoformat(result_dict["started_at"]) if result_dict["started_at"] else None,
        completed_at=datetime.fromisoformat(result_dict["completed_at"]) if result_dict["completed_at"] else None,
        urls_discovered=result_dict["urls_discovered"],
        urls_fetched=result_dict["urls_fetched"],
        listings_created=result_dict["listings_created"],
        entities_created=result_dict["entities_created"],
        entities_matched=result_dict["entities_matched"],
        review_queue_count=result_dict["review_queue_count"],
        errors=result_dict["errors"],
        duration_seconds=result_dict["duration_seconds"],
    )


async def enqueue_ingestion(
    source_name: str,
    max_urls: int | None = None,
) -> str:
    """
    Enqueue an ingestion job for async processing.

    Args:
        source_name: Name of the source to ingest
        max_urls: Optional limit on URLs to process

    Returns:
        Job ID
    """
    redis = await create_pool(get_redis_settings())
    job = await redis.enqueue_job("ingest_source", source_name, max_urls)
    await redis.close()
    return job.job_id


async def get_job_status(job_id: str) -> dict[str, Any] | None:
    """
    Get the status of an ingestion job.

    Args:
        job_id: Job ID to look up

    Returns:
        Job info dict, or None if not found
    """
    redis = await create_pool(get_redis_settings())
    job = await redis.job(job_id)

    if job is None:
        await redis.close()
        return None

    info = await job.info()
    result = await job.result()
    await redis.close()

    return {
        "job_id": job_id,
        "status": info.status if info else "unknown",
        "result": result,
    }


class WorkerSettings:
    """arq worker settings."""

    functions = [ingest_source]
    redis_settings = get_redis_settings()
    max_jobs = 5
    job_timeout = 3600  # 1 hour
    keep_result = 86400  # 24 hours
