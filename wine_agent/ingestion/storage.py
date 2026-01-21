"""
Snapshot Storage Module
=======================

Provides abstract and concrete implementations for storing
raw content snapshots from crawled pages.
"""

from __future__ import annotations

import gzip
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import BinaryIO
from uuid import UUID, uuid4


@dataclass
class SnapshotMetadata:
    """Metadata about a stored snapshot."""

    snapshot_id: UUID
    source_id: UUID
    url: str
    content_hash: str
    mime_type: str
    size_bytes: int
    compressed_size_bytes: int
    created_at: datetime
    file_path: str


class SnapshotStorage(ABC):
    """
    Abstract base class for snapshot storage.

    Implementations should handle saving and retrieving raw
    content snapshots from crawled pages.
    """

    @abstractmethod
    def save_snapshot(
        self,
        content: bytes,
        source_id: UUID,
        url: str,
        content_hash: str,
        mime_type: str,
    ) -> SnapshotMetadata:
        """
        Save a content snapshot.

        Args:
            content: Raw content bytes
            source_id: ID of the source this content came from
            url: Original URL of the content
            content_hash: Pre-computed hash of the content
            mime_type: MIME type of the content

        Returns:
            SnapshotMetadata with storage details
        """
        pass

    @abstractmethod
    def get_snapshot(self, snapshot_id: UUID) -> bytes | None:
        """
        Retrieve a snapshot by ID.

        Args:
            snapshot_id: Snapshot UUID

        Returns:
            Raw content bytes, or None if not found
        """
        pass

    @abstractmethod
    def get_snapshot_by_hash(self, content_hash: str) -> SnapshotMetadata | None:
        """
        Find a snapshot by its content hash.

        Args:
            content_hash: SHA-256 hash of the content

        Returns:
            SnapshotMetadata if found, None otherwise
        """
        pass

    @abstractmethod
    def delete_snapshot(self, snapshot_id: UUID) -> bool:
        """
        Delete a snapshot.

        Args:
            snapshot_id: Snapshot UUID

        Returns:
            True if deleted, False if not found
        """
        pass

    @abstractmethod
    def list_snapshots(
        self,
        source_id: UUID | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[SnapshotMetadata]:
        """
        List snapshots with optional filtering.

        Args:
            source_id: Filter by source ID (optional)
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            List of SnapshotMetadata
        """
        pass


class LocalFileStorage(SnapshotStorage):
    """
    Local filesystem storage for snapshots.

    Directory structure:
        {base_path}/YYYY/MM/DD/{hash[:2]}/{snapshot_id}.{ext}.gz

    Files are gzip compressed to save space. A JSON index file
    tracks metadata for each snapshot.
    """

    # Map MIME types to file extensions
    MIME_EXTENSIONS = {
        "text/html": "html",
        "application/json": "json",
        "application/xml": "xml",
        "text/xml": "xml",
        "text/plain": "txt",
    }

    def __init__(self, base_path: str | Path) -> None:
        """
        Initialize local file storage.

        Args:
            base_path: Base directory for storing snapshots
        """
        self.base_path = Path(base_path).expanduser().resolve()
        self.base_path.mkdir(parents=True, exist_ok=True)

        # In-memory index for quick lookups (in production, use SQLite or similar)
        self._hash_index: dict[str, SnapshotMetadata] = {}
        self._id_index: dict[UUID, SnapshotMetadata] = {}

    def _get_extension(self, mime_type: str) -> str:
        """Get file extension for a MIME type."""
        return self.MIME_EXTENSIONS.get(mime_type, "bin")

    def _get_snapshot_path(
        self,
        snapshot_id: UUID,
        content_hash: str,
        created_at: datetime,
        extension: str,
    ) -> Path:
        """
        Generate the storage path for a snapshot.

        Structure: {base}/YYYY/MM/DD/{hash[:2]}/{snapshot_id}.{ext}.gz
        """
        date_path = created_at.strftime("%Y/%m/%d")
        hash_prefix = content_hash[:2]
        filename = f"{snapshot_id}.{extension}.gz"
        return self.base_path / date_path / hash_prefix / filename

    def save_snapshot(
        self,
        content: bytes,
        source_id: UUID,
        url: str,
        content_hash: str,
        mime_type: str,
    ) -> SnapshotMetadata:
        """Save a content snapshot to local filesystem."""
        # Check if we already have this content
        existing = self._hash_index.get(content_hash)
        if existing:
            return existing

        snapshot_id = uuid4()
        created_at = datetime.utcnow()
        extension = self._get_extension(mime_type)

        # Generate path and ensure directory exists
        file_path = self._get_snapshot_path(snapshot_id, content_hash, created_at, extension)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Compress and save
        compressed = gzip.compress(content, compresslevel=6)
        with open(file_path, "wb") as f:
            f.write(compressed)

        # Create metadata
        metadata = SnapshotMetadata(
            snapshot_id=snapshot_id,
            source_id=source_id,
            url=url,
            content_hash=content_hash,
            mime_type=mime_type,
            size_bytes=len(content),
            compressed_size_bytes=len(compressed),
            created_at=created_at,
            file_path=str(file_path),
        )

        # Update indices
        self._hash_index[content_hash] = metadata
        self._id_index[snapshot_id] = metadata

        return metadata

    def get_snapshot(self, snapshot_id: UUID) -> bytes | None:
        """Retrieve a snapshot by ID."""
        metadata = self._id_index.get(snapshot_id)
        if metadata is None:
            return None

        file_path = Path(metadata.file_path)
        if not file_path.exists():
            return None

        with open(file_path, "rb") as f:
            compressed = f.read()
        return gzip.decompress(compressed)

    def get_snapshot_by_hash(self, content_hash: str) -> SnapshotMetadata | None:
        """Find a snapshot by its content hash."""
        return self._hash_index.get(content_hash)

    def delete_snapshot(self, snapshot_id: UUID) -> bool:
        """Delete a snapshot."""
        metadata = self._id_index.get(snapshot_id)
        if metadata is None:
            return False

        # Remove file
        file_path = Path(metadata.file_path)
        if file_path.exists():
            file_path.unlink()

        # Update indices
        del self._id_index[snapshot_id]
        if metadata.content_hash in self._hash_index:
            del self._hash_index[metadata.content_hash]

        return True

    def list_snapshots(
        self,
        source_id: UUID | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[SnapshotMetadata]:
        """List snapshots with optional filtering."""
        snapshots = list(self._id_index.values())

        # Filter by source if specified
        if source_id:
            snapshots = [s for s in snapshots if s.source_id == source_id]

        # Sort by created_at descending
        snapshots.sort(key=lambda s: s.created_at, reverse=True)

        # Apply pagination
        return snapshots[offset : offset + limit]

    def get_storage_stats(self) -> dict:
        """Get storage statistics."""
        total_size = 0
        total_compressed = 0
        count = 0

        for metadata in self._id_index.values():
            total_size += metadata.size_bytes
            total_compressed += metadata.compressed_size_bytes
            count += 1

        return {
            "total_snapshots": count,
            "total_size_bytes": total_size,
            "total_compressed_bytes": total_compressed,
            "compression_ratio": total_compressed / total_size if total_size > 0 else 0,
        }


def get_default_storage() -> LocalFileStorage:
    """
    Get the default storage instance.

    Uses SNAPSHOT_STORAGE_PATH environment variable or defaults
    to ~/.wine_agent/snapshots.
    """
    storage_path = os.environ.get(
        "SNAPSHOT_STORAGE_PATH", "~/.wine_agent/snapshots"
    )
    return LocalFileStorage(storage_path)
