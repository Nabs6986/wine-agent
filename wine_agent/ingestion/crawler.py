"""
Web Crawler Module
==================

Provides HTTP fetching with robots.txt compliance, rate limiting,
and content deduplication.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx

if TYPE_CHECKING:
    from wine_agent.ingestion.registry import SourceConfig

logger = logging.getLogger(__name__)


@dataclass
class FetchResult:
    """Result of fetching a URL."""

    url: str
    content: bytes
    content_hash: str
    mime_type: str
    status_code: int
    fetched_at: datetime
    is_duplicate: bool = False
    error: str | None = None

    @property
    def success(self) -> bool:
        """Check if fetch was successful."""
        return self.error is None and 200 <= self.status_code < 300


class TokenBucket:
    """
    Token bucket rate limiter for per-domain rate limiting.

    Allows bursting up to burst_limit requests, then enforces
    the steady-state rate of requests_per_second.
    """

    def __init__(self, requests_per_second: float, burst_limit: int) -> None:
        self.requests_per_second = requests_per_second
        self.burst_limit = burst_limit
        self.tokens = float(burst_limit)
        self.last_update = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """
        Acquire a token, waiting if necessary.

        This method blocks until a token is available.
        """
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self.last_update
            self.last_update = now

            # Add tokens based on elapsed time
            self.tokens = min(
                self.burst_limit, self.tokens + elapsed * self.requests_per_second
            )

            if self.tokens < 1.0:
                # Need to wait for tokens
                wait_time = (1.0 - self.tokens) / self.requests_per_second
                await asyncio.sleep(wait_time)
                self.tokens = 0.0
            else:
                self.tokens -= 1.0


class RobotsChecker:
    """
    Robots.txt parser and cache.

    Caches parsed robots.txt files per domain and checks
    if URLs are allowed for crawling.
    """

    def __init__(self, user_agent: str, timeout: float = 10.0) -> None:
        self.user_agent = user_agent
        self.timeout = timeout
        self._cache: dict[str, RobotFileParser | None] = {}
        self._lock = asyncio.Lock()

    async def _fetch_robots(self, domain: str, scheme: str = "https") -> RobotFileParser | None:
        """Fetch and parse robots.txt for a domain."""
        robots_url = f"{scheme}://{domain}/robots.txt"

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    robots_url,
                    headers={"User-Agent": self.user_agent},
                    follow_redirects=True,
                )

                if response.status_code == 200:
                    parser = RobotFileParser()
                    parser.parse(response.text.splitlines())
                    return parser
                else:
                    # No robots.txt or error - allow all
                    return None
        except Exception as e:
            logger.warning(f"Failed to fetch robots.txt for {domain}: {e}")
            return None

    async def is_allowed(self, url: str) -> bool:
        """
        Check if a URL is allowed by robots.txt.

        Args:
            url: Full URL to check

        Returns:
            True if allowed, False if disallowed
        """
        parsed = urlparse(url)
        domain = parsed.netloc
        scheme = parsed.scheme or "https"

        async with self._lock:
            if domain not in self._cache:
                self._cache[domain] = await self._fetch_robots(domain, scheme)

        parser = self._cache.get(domain)
        if parser is None:
            # No robots.txt - allow everything
            return True

        return parser.can_fetch(self.user_agent, url)

    def clear_cache(self) -> None:
        """Clear the robots.txt cache."""
        self._cache.clear()


class Crawler:
    """
    Web crawler with rate limiting and robots.txt compliance.

    Features:
    - Per-domain rate limiting with token bucket algorithm
    - Robots.txt compliance
    - Content hashing for deduplication
    - Configurable timeouts and retries
    """

    def __init__(
        self,
        user_agent: str = "WineAgent/0.1",
        timeout: float = 30.0,
        max_retries: int = 3,
        respect_robots: bool = True,
    ) -> None:
        self.user_agent = user_agent
        self.timeout = timeout
        self.max_retries = max_retries
        self.respect_robots = respect_robots

        self._rate_limiters: dict[str, TokenBucket] = {}
        self._robots_checker = RobotsChecker(user_agent) if respect_robots else None
        self._seen_hashes: set[str] = set()

    def _get_rate_limiter(self, source: SourceConfig) -> TokenBucket:
        """Get or create a rate limiter for a source."""
        if source.name not in self._rate_limiters:
            self._rate_limiters[source.name] = TokenBucket(
                requests_per_second=source.rate_limit.requests_per_second,
                burst_limit=source.rate_limit.burst_limit,
            )
        return self._rate_limiters[source.name]

    @staticmethod
    def compute_hash(content: bytes) -> str:
        """
        Compute SHA-256 hash of content.

        Args:
            content: Raw bytes to hash

        Returns:
            Hex-encoded SHA-256 hash
        """
        return hashlib.sha256(content).hexdigest()

    async def fetch(self, url: str, source: SourceConfig) -> FetchResult:
        """
        Fetch a URL with rate limiting and robots.txt compliance.

        Args:
            url: URL to fetch
            source: Source configuration for rate limiting

        Returns:
            FetchResult with content or error
        """
        fetched_at = datetime.utcnow()

        # Check if URL is allowed by source config
        if not source.is_url_allowed(url):
            return FetchResult(
                url=url,
                content=b"",
                content_hash="",
                mime_type="",
                status_code=0,
                fetched_at=fetched_at,
                error=f"URL not allowed by source '{source.name}' configuration",
            )

        # Check robots.txt
        if self._robots_checker:
            try:
                allowed = await self._robots_checker.is_allowed(url)
                if not allowed:
                    return FetchResult(
                        url=url,
                        content=b"",
                        content_hash="",
                        mime_type="",
                        status_code=0,
                        fetched_at=fetched_at,
                        error="Disallowed by robots.txt",
                    )
            except Exception as e:
                logger.warning(f"Robots.txt check failed for {url}: {e}")

        # Apply rate limiting
        rate_limiter = self._get_rate_limiter(source)
        await rate_limiter.acquire()

        # Fetch with retries
        last_error: str | None = None
        for attempt in range(self.max_retries):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.get(
                        url,
                        headers={"User-Agent": self.user_agent},
                        follow_redirects=True,
                    )

                    content = response.content
                    content_hash = self.compute_hash(content)
                    mime_type = response.headers.get("content-type", "").split(";")[0].strip()

                    # Check for duplicate content
                    is_duplicate = content_hash in self._seen_hashes
                    if not is_duplicate:
                        self._seen_hashes.add(content_hash)

                    return FetchResult(
                        url=url,
                        content=content,
                        content_hash=content_hash,
                        mime_type=mime_type,
                        status_code=response.status_code,
                        fetched_at=fetched_at,
                        is_duplicate=is_duplicate,
                    )

            except httpx.TimeoutException:
                last_error = f"Timeout after {self.timeout}s"
                logger.warning(f"Timeout fetching {url} (attempt {attempt + 1}/{self.max_retries})")
            except httpx.HTTPError as e:
                last_error = str(e)
                logger.warning(f"HTTP error fetching {url}: {e} (attempt {attempt + 1}/{self.max_retries})")
            except Exception as e:
                last_error = str(e)
                logger.error(f"Unexpected error fetching {url}: {e}")
                break  # Don't retry unexpected errors

            # Wait before retry with exponential backoff
            if attempt < self.max_retries - 1:
                await asyncio.sleep(2**attempt)

        return FetchResult(
            url=url,
            content=b"",
            content_hash="",
            mime_type="",
            status_code=0,
            fetched_at=fetched_at,
            error=last_error or "Unknown error",
        )

    async def fetch_batch(
        self,
        urls: list[str],
        source: SourceConfig,
        concurrency: int = 5,
    ) -> list[FetchResult]:
        """
        Fetch multiple URLs with controlled concurrency.

        Args:
            urls: List of URLs to fetch
            source: Source configuration
            concurrency: Maximum concurrent requests

        Returns:
            List of FetchResults in the same order as input URLs
        """
        semaphore = asyncio.Semaphore(concurrency)

        async def fetch_with_semaphore(url: str) -> FetchResult:
            async with semaphore:
                return await self.fetch(url, source)

        tasks = [fetch_with_semaphore(url) for url in urls]
        return await asyncio.gather(*tasks)

    def clear_seen_hashes(self) -> None:
        """Clear the set of seen content hashes."""
        self._seen_hashes.clear()

    def mark_hash_seen(self, content_hash: str) -> None:
        """Mark a content hash as already seen (for deduplication)."""
        self._seen_hashes.add(content_hash)
