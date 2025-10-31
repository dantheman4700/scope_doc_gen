"""Filesystem-backed storage backend."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import List, Optional

from .base import StorageBackend, StorageObject


class LocalStorageBackend(StorageBackend):
    """Store files on the local filesystem under a base directory."""

    def __init__(self, base_dir: Path) -> None:
        self._base_dir = base_dir.resolve()
        self._base_dir.mkdir(parents=True, exist_ok=True)

    def _resolve(self, key: str) -> Path:
        target = self._base_dir / key
        target.parent.mkdir(parents=True, exist_ok=True)
        return target

    def put_bytes(self, key: str, data: bytes, content_type: Optional[str] = None) -> StorageObject:
        target = self._resolve(key)
        target.write_bytes(data)
        return StorageObject(key=key, size=len(data))

    def upload_file(self, key: str, source_path: Path, content_type: Optional[str] = None) -> StorageObject:
        source = source_path.resolve()
        if not source.exists():
            raise FileNotFoundError(source)
        target = self._resolve(key)
        shutil.copy2(source, target)
        size = target.stat().st_size
        return StorageObject(key=key, size=size)

    def download_to_path(self, key: str, destination: Path) -> None:
        source = self._resolve(key)
        if not source.exists():
            raise FileNotFoundError(source)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)

    def delete(self, key: str) -> None:
        target = self._base_dir / key
        if target.exists():
            target.unlink()

    def list(self, prefix: str) -> List[StorageObject]:
        base = (self._base_dir / prefix).resolve()
        objects: List[StorageObject] = []
        if base.is_file():
            stat = base.stat()
            rel_key = str(base.relative_to(self._base_dir))
            objects.append(StorageObject(key=rel_key, size=stat.st_size))
            return objects
        if not base.exists():
            return []
        for path in base.rglob("*"):
            if path.is_file():
                rel = path.relative_to(self._base_dir)
                objects.append(StorageObject(key=str(rel), size=path.stat().st_size))
        return objects


