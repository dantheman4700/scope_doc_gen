"""Base storage backend definitions."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


@dataclass
class StorageObject:
    """Represents a stored object's metadata."""

    key: str
    size: Optional[int] = None
    checksum: Optional[str] = None
    content_type: Optional[str] = None


class StorageError(RuntimeError):
    """Raised when storage operations fail."""


class StorageBackend:
    """Abstract interface for storage backends."""

    def put_bytes(self, key: str, data: bytes, content_type: Optional[str] = None) -> StorageObject:
        raise NotImplementedError

    def upload_file(self, key: str, source_path: Path, content_type: Optional[str] = None) -> StorageObject:
        raise NotImplementedError

    def download_to_path(self, key: str, destination: Path) -> None:
        raise NotImplementedError

    def delete(self, key: str) -> None:
        raise NotImplementedError

    def list(self, prefix: str) -> List[StorageObject]:
        raise NotImplementedError

    def generate_signed_url(self, key: str, expires_in_seconds: int = 3600) -> Optional[str]:
        return None


