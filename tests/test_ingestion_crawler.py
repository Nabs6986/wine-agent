"""Tests for the ingestion crawler module."""

import asyncio
import time

import pytest

from wine_agent.ingestion.crawler import Crawler, FetchResult, TokenBucket
from wine_agent.ingestion.registry import RateLimitConfig, SourceConfig


class TestTokenBucket:
    """Tests for the TokenBucket rate limiter."""

    @pytest.mark.asyncio
    async def test_initial_burst(self) -> None:
        """Test that initial requests use burst tokens."""
        bucket = TokenBucket(requests_per_second=1.0, burst_limit=5)

        # Should be able to make 5 requests immediately
        start = time.monotonic()
        for _ in range(5):
            await bucket.acquire()
        elapsed = time.monotonic() - start

        # All 5 should complete quickly (within 0.1s)
        assert elapsed < 0.1

    @pytest.mark.asyncio
    async def test_rate_limiting(self) -> None:
        """Test that requests are rate limited after burst."""
        bucket = TokenBucket(requests_per_second=10.0, burst_limit=1)

        # First request should be immediate
        await bucket.acquire()

        # Second request should wait ~0.1s
        start = time.monotonic()
        await bucket.acquire()
        elapsed = time.monotonic() - start

        # Should take approximately 0.1s (1/10 second)
        assert 0.05 < elapsed < 0.3

    @pytest.mark.asyncio
    async def test_token_refill(self) -> None:
        """Test that tokens refill over time."""
        bucket = TokenBucket(requests_per_second=10.0, burst_limit=2)

        # Use up burst tokens
        await bucket.acquire()
        await bucket.acquire()

        # Wait for tokens to refill
        await asyncio.sleep(0.2)  # Should get ~2 tokens back

        # Should be able to acquire immediately
        start = time.monotonic()
        await bucket.acquire()
        elapsed = time.monotonic() - start

        assert elapsed < 0.1


class TestFetchResult:
    """Tests for the FetchResult dataclass."""

    def test_success(self) -> None:
        """Test success property for successful fetch."""
        from datetime import datetime

        result = FetchResult(
            url="https://example.com",
            content=b"test",
            content_hash="abc123",
            mime_type="text/html",
            status_code=200,
            fetched_at=datetime.utcnow(),
        )
        assert result.success is True

    def test_success_with_error(self) -> None:
        """Test success property when error is set."""
        from datetime import datetime

        result = FetchResult(
            url="https://example.com",
            content=b"",
            content_hash="",
            mime_type="",
            status_code=0,
            fetched_at=datetime.utcnow(),
            error="Connection failed",
        )
        assert result.success is False

    def test_success_non_200(self) -> None:
        """Test success property for non-200 status codes."""
        from datetime import datetime

        result = FetchResult(
            url="https://example.com",
            content=b"",
            content_hash="",
            mime_type="",
            status_code=404,
            fetched_at=datetime.utcnow(),
        )
        assert result.success is False


class TestCrawler:
    """Tests for the Crawler class."""

    @pytest.fixture
    def source_config(self) -> SourceConfig:
        """Create a test source configuration."""
        return SourceConfig(
            name="test",
            domain="test.example.com",
            adapter="test",
            rate_limit=RateLimitConfig(requests_per_second=10.0, burst_limit=5),
            allowlist=["^https://test\\.example\\.com/.*"],
        )

    def test_compute_hash(self) -> None:
        """Test content hash computation."""
        crawler = Crawler()
        content = b"test content"
        hash1 = crawler.compute_hash(content)
        hash2 = crawler.compute_hash(content)

        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256 hex length

    def test_compute_hash_different_content(self) -> None:
        """Test that different content produces different hashes."""
        crawler = Crawler()
        hash1 = crawler.compute_hash(b"content 1")
        hash2 = crawler.compute_hash(b"content 2")

        assert hash1 != hash2

    def test_mark_hash_seen(self) -> None:
        """Test marking hashes as seen."""
        crawler = Crawler()
        test_hash = "abc123"

        assert test_hash not in crawler._seen_hashes
        crawler.mark_hash_seen(test_hash)
        assert test_hash in crawler._seen_hashes

    def test_clear_seen_hashes(self) -> None:
        """Test clearing seen hashes."""
        crawler = Crawler()
        crawler.mark_hash_seen("hash1")
        crawler.mark_hash_seen("hash2")

        assert len(crawler._seen_hashes) == 2
        crawler.clear_seen_hashes()
        assert len(crawler._seen_hashes) == 0

    @pytest.mark.asyncio
    async def test_fetch_url_not_allowed(self, source_config: SourceConfig) -> None:
        """Test fetch fails for URLs not matching allowlist."""
        crawler = Crawler(respect_robots=False)
        result = await crawler.fetch(
            "https://other.example.com/page",
            source_config,
        )

        assert result.success is False
        assert "not allowed" in result.error.lower()

    def test_rate_limiter_creation(self, source_config: SourceConfig) -> None:
        """Test that rate limiters are created per source."""
        crawler = Crawler()

        limiter1 = crawler._get_rate_limiter(source_config)
        limiter2 = crawler._get_rate_limiter(source_config)

        # Should return the same limiter for the same source
        assert limiter1 is limiter2

    def test_rate_limiter_config(self, source_config: SourceConfig) -> None:
        """Test that rate limiter uses source config."""
        crawler = Crawler()
        limiter = crawler._get_rate_limiter(source_config)

        assert limiter.requests_per_second == 10.0
        assert limiter.burst_limit == 5


class TestRobotsChecker:
    """Tests for robots.txt compliance."""

    def test_crawler_respects_robots_flag(self) -> None:
        """Test that respect_robots flag is properly set."""
        crawler1 = Crawler(respect_robots=True)
        crawler2 = Crawler(respect_robots=False)

        assert crawler1._robots_checker is not None
        assert crawler2._robots_checker is None
