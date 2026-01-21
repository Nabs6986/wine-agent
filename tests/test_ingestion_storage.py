"""Tests for the ingestion storage module."""

import tempfile
from pathlib import Path
from uuid import uuid4

import pytest

from wine_agent.ingestion.storage import LocalFileStorage, SnapshotMetadata


class TestLocalFileStorage:
    """Tests for LocalFileStorage."""

    @pytest.fixture
    def storage(self) -> LocalFileStorage:
        """Create a storage instance with a temp directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield LocalFileStorage(tmpdir)

    @pytest.fixture
    def sample_content(self) -> bytes:
        """Sample content for testing."""
        return b"<html><body>Test wine page content</body></html>"

    def test_save_snapshot(self, storage: LocalFileStorage, sample_content: bytes) -> None:
        """Test saving a snapshot."""
        source_id = uuid4()
        url = "https://example.com/wine/1"
        content_hash = "abc123"

        metadata = storage.save_snapshot(
            content=sample_content,
            source_id=source_id,
            url=url,
            content_hash=content_hash,
            mime_type="text/html",
        )

        assert metadata.source_id == source_id
        assert metadata.url == url
        assert metadata.content_hash == content_hash
        assert metadata.mime_type == "text/html"
        assert metadata.size_bytes == len(sample_content)
        # Note: Small content may have larger compressed size due to gzip header overhead
        assert metadata.compressed_size_bytes > 0

    def test_get_snapshot(self, storage: LocalFileStorage, sample_content: bytes) -> None:
        """Test retrieving a snapshot."""
        source_id = uuid4()

        metadata = storage.save_snapshot(
            content=sample_content,
            source_id=source_id,
            url="https://example.com/wine/1",
            content_hash="abc123",
            mime_type="text/html",
        )

        retrieved = storage.get_snapshot(metadata.snapshot_id)
        assert retrieved == sample_content

    def test_get_snapshot_not_found(self, storage: LocalFileStorage) -> None:
        """Test retrieving a non-existent snapshot."""
        retrieved = storage.get_snapshot(uuid4())
        assert retrieved is None

    def test_get_snapshot_by_hash(self, storage: LocalFileStorage, sample_content: bytes) -> None:
        """Test finding a snapshot by content hash."""
        source_id = uuid4()
        content_hash = "unique_hash_123"

        metadata = storage.save_snapshot(
            content=sample_content,
            source_id=source_id,
            url="https://example.com/wine/1",
            content_hash=content_hash,
            mime_type="text/html",
        )

        found = storage.get_snapshot_by_hash(content_hash)
        assert found is not None
        assert found.snapshot_id == metadata.snapshot_id

    def test_get_snapshot_by_hash_not_found(self, storage: LocalFileStorage) -> None:
        """Test finding a non-existent hash."""
        found = storage.get_snapshot_by_hash("non_existent_hash")
        assert found is None

    def test_deduplication(self, storage: LocalFileStorage, sample_content: bytes) -> None:
        """Test that duplicate content returns existing metadata."""
        source_id = uuid4()
        content_hash = "duplicate_hash"

        # Save first snapshot
        metadata1 = storage.save_snapshot(
            content=sample_content,
            source_id=source_id,
            url="https://example.com/wine/1",
            content_hash=content_hash,
            mime_type="text/html",
        )

        # Try to save duplicate
        metadata2 = storage.save_snapshot(
            content=sample_content,
            source_id=source_id,
            url="https://example.com/wine/2",  # Different URL
            content_hash=content_hash,  # Same hash
            mime_type="text/html",
        )

        # Should return the same snapshot
        assert metadata1.snapshot_id == metadata2.snapshot_id

    def test_delete_snapshot(self, storage: LocalFileStorage, sample_content: bytes) -> None:
        """Test deleting a snapshot."""
        source_id = uuid4()

        metadata = storage.save_snapshot(
            content=sample_content,
            source_id=source_id,
            url="https://example.com/wine/1",
            content_hash="delete_test",
            mime_type="text/html",
        )

        # Verify it exists
        assert storage.get_snapshot(metadata.snapshot_id) is not None

        # Delete it
        result = storage.delete_snapshot(metadata.snapshot_id)
        assert result is True

        # Verify it's gone
        assert storage.get_snapshot(metadata.snapshot_id) is None

    def test_delete_snapshot_not_found(self, storage: LocalFileStorage) -> None:
        """Test deleting a non-existent snapshot."""
        result = storage.delete_snapshot(uuid4())
        assert result is False

    def test_list_snapshots(self, storage: LocalFileStorage) -> None:
        """Test listing snapshots."""
        source_id = uuid4()

        # Create multiple snapshots
        for i in range(5):
            storage.save_snapshot(
                content=f"content {i}".encode(),
                source_id=source_id,
                url=f"https://example.com/wine/{i}",
                content_hash=f"hash_{i}",
                mime_type="text/html",
            )

        snapshots = storage.list_snapshots()
        assert len(snapshots) == 5

    def test_list_snapshots_with_filter(self, storage: LocalFileStorage) -> None:
        """Test listing snapshots with source filter."""
        source1_id = uuid4()
        source2_id = uuid4()

        # Create snapshots for source 1
        for i in range(3):
            storage.save_snapshot(
                content=f"source1 content {i}".encode(),
                source_id=source1_id,
                url=f"https://source1.com/{i}",
                content_hash=f"s1_hash_{i}",
                mime_type="text/html",
            )

        # Create snapshots for source 2
        for i in range(2):
            storage.save_snapshot(
                content=f"source2 content {i}".encode(),
                source_id=source2_id,
                url=f"https://source2.com/{i}",
                content_hash=f"s2_hash_{i}",
                mime_type="text/html",
            )

        # Filter by source
        source1_snapshots = storage.list_snapshots(source_id=source1_id)
        assert len(source1_snapshots) == 3

        source2_snapshots = storage.list_snapshots(source_id=source2_id)
        assert len(source2_snapshots) == 2

    def test_list_snapshots_pagination(self, storage: LocalFileStorage) -> None:
        """Test listing snapshots with pagination."""
        source_id = uuid4()

        # Create 10 snapshots
        for i in range(10):
            storage.save_snapshot(
                content=f"content {i}".encode(),
                source_id=source_id,
                url=f"https://example.com/{i}",
                content_hash=f"hash_{i}",
                mime_type="text/html",
            )

        # Get first page
        page1 = storage.list_snapshots(limit=5, offset=0)
        assert len(page1) == 5

        # Get second page
        page2 = storage.list_snapshots(limit=5, offset=5)
        assert len(page2) == 5

        # Verify no overlap
        page1_ids = {s.snapshot_id for s in page1}
        page2_ids = {s.snapshot_id for s in page2}
        assert page1_ids.isdisjoint(page2_ids)

    def test_storage_stats(self, storage: LocalFileStorage, sample_content: bytes) -> None:
        """Test getting storage statistics."""
        source_id = uuid4()

        # Initially empty
        stats = storage.get_storage_stats()
        assert stats["total_snapshots"] == 0

        # Add some snapshots
        for i in range(3):
            storage.save_snapshot(
                content=f"content {i} with more text".encode() * 100,
                source_id=source_id,
                url=f"https://example.com/{i}",
                content_hash=f"hash_{i}",
                mime_type="text/html",
            )

        stats = storage.get_storage_stats()
        assert stats["total_snapshots"] == 3
        assert stats["total_size_bytes"] > 0
        assert stats["total_compressed_bytes"] > 0
        assert stats["compression_ratio"] < 1.0  # Should be compressed

    def test_file_path_structure(self, storage: LocalFileStorage, sample_content: bytes) -> None:
        """Test that file paths follow expected structure."""
        source_id = uuid4()
        content_hash = "abcdef1234567890"

        metadata = storage.save_snapshot(
            content=sample_content,
            source_id=source_id,
            url="https://example.com/wine/1",
            content_hash=content_hash,
            mime_type="text/html",
        )

        path = Path(metadata.file_path)

        # Should be a .gz file
        assert path.suffix == ".gz"

        # Should contain hash prefix in path
        assert content_hash[:2] in str(path)

        # File should exist
        assert path.exists()

    def test_mime_type_extensions(self, storage: LocalFileStorage) -> None:
        """Test that correct extensions are used for MIME types."""
        source_id = uuid4()

        # HTML
        html_meta = storage.save_snapshot(
            content=b"<html></html>",
            source_id=source_id,
            url="https://example.com/1",
            content_hash="hash_html",
            mime_type="text/html",
        )
        assert ".html.gz" in html_meta.file_path

        # JSON
        json_meta = storage.save_snapshot(
            content=b"{}",
            source_id=source_id,
            url="https://example.com/2",
            content_hash="hash_json",
            mime_type="application/json",
        )
        assert ".json.gz" in json_meta.file_path

        # Unknown type defaults to .bin
        bin_meta = storage.save_snapshot(
            content=b"binary",
            source_id=source_id,
            url="https://example.com/3",
            content_hash="hash_bin",
            mime_type="application/octet-stream",
        )
        assert ".bin.gz" in bin_meta.file_path
