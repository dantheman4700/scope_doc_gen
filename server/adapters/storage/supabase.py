"""Supabase storage backend implementation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import httpx

from .base import StorageBackend, StorageError, StorageObject


@dataclass
class _SupabaseConfig:
    url: str
    bucket: str
    service_role_key: str


class SupabaseStorageBackend(StorageBackend):
    """Interact with Supabase Storage using the service role key."""

    def __init__(self, *, url: str, bucket: str, service_role_key: str, timeout: float = 60.0) -> None:
        if not url:
            raise StorageError("SUPABASE_URL is not configured")
        if not service_role_key:
            raise StorageError("SUPABASE_SERVICE_ROLE_KEY is not configured")
        if not bucket:
            raise StorageError("SUPABASE_BUCKET is not configured")

        self._config = _SupabaseConfig(url=url.rstrip("/"), bucket=bucket, service_role_key=service_role_key)
        self._client = httpx.Client(
            base_url=f"{self._config.url}/storage/v1",
            headers={
                "Authorization": f"Bearer {self._config.service_role_key}",
                "apikey": self._config.service_role_key,
            },
            timeout=timeout,
        )

    def close(self) -> None:  # pragma: no cover - convenience helper
        self._client.close()

    # ------------------------------------------------------------------
    # StorageBackend interface
    # ------------------------------------------------------------------
    def put_bytes(self, key: str, data: bytes, content_type: Optional[str] = None) -> StorageObject:
        return self._upload(key, data=data, content_type=content_type)

    def upload_file(self, key: str, source_path: Path, content_type: Optional[str] = None) -> StorageObject:
        path = source_path.resolve()
        if not path.exists():
            raise FileNotFoundError(path)
        data = path.read_bytes()
        return self._upload(key, data=data, content_type=content_type)

    def download_to_path(self, key: str, destination: Path) -> None:
        response = self._client.get(f"/object/{self._config.bucket}/{key}")
        if response.status_code >= 400:
            raise StorageError(f"Failed to download '{key}': {response.status_code} {response.text}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(response.content)

    def delete(self, key: str) -> None:
        payload = {"paths": [key]}
        response = self._client.post(f"/object/delete/{self._config.bucket}", json=payload)
        if response.status_code >= 400:
            raise StorageError(f"Failed to delete '{key}': {response.status_code} {response.text}")

    def list(self, prefix: str) -> List[StorageObject]:
        objects: List[StorageObject] = []
        page = 0
        page_size = 1000
        while True:
            payload = {
                "prefix": prefix,
                "limit": page_size,
                "offset": page * page_size,
                "sortBy": {"column": "name", "order": "asc"},
            }
            response = self._client.post(f"/object/list/{self._config.bucket}", json=payload)
            if response.status_code >= 400:
                raise StorageError(
                    f"Failed to list prefix '{prefix}': {response.status_code} {response.text}"
                )
            data = response.json()
            if not data:
                break
            for entry in data:
                name = entry.get("name")
                if not name:
                    continue
                size = entry.get("metadata", {}).get("size")
                objects.append(StorageObject(key=f"{prefix}/{name}" if prefix else name, size=size))
            if len(data) < page_size:
                break
            page += 1
        return objects

    def generate_signed_url(self, key: str, expires_in_seconds: int = 3600) -> Optional[str]:
        payload = {"expiresIn": expires_in_seconds}
        response = self._client.post(f"/object/sign/{self._config.bucket}/{key}", json=payload)
        if response.status_code >= 400:
            raise StorageError(
                f"Failed to sign URL for '{key}': {response.status_code} {response.text}"
            )
        body = response.json()
        signed_path = body.get("signedURL") or body.get("signedUrl")
        if not signed_path:
            return None
        if signed_path.startswith("http"):
            return signed_path
        return f"{self._config.url}/storage/v1{signed_path}"

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _upload(self, key: str, *, data: bytes, content_type: Optional[str]) -> StorageObject:
        headers = {"content-type": content_type} if content_type else None
        response = self._client.post(
            f"/object/{self._config.bucket}/{key}",
            content=data,
            headers=headers,
            params={"upsert": "true"},
        )
        if response.status_code >= 400:
            raise StorageError(f"Failed to upload '{key}': {response.status_code} {response.text}")
        return StorageObject(key=key, size=len(data), content_type=content_type)


