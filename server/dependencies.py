"""FastAPI dependencies common across routes."""

from __future__ import annotations

from functools import lru_cache
from typing import Iterator

from fastapi import Depends
from sqlalchemy.orm import Session

from .adapters.auth import AuthProvider, LocalAuthProvider, SupabaseAuthProvider
from .adapters.storage import LocalStorageBackend, StorageBackend, SupabaseStorageBackend
from .core.config import (
    AUTH_PROVIDER,
    DATA_ROOT,
    PROJECTS_DATA_DIR,
    STORAGE_PROVIDER,
    SUPABASE_ANON_KEY,
    SUPABASE_BUCKET,
    SUPABASE_SERVICE_ROLE_KEY,
    SUPABASE_URL,
)
from .db.session import get_session


def db_session() -> Iterator[Session]:
    with get_session() as session:
        yield session


@lru_cache(maxsize=1)
def _storage_backend() -> StorageBackend:
    if STORAGE_PROVIDER == "supabase":
        missing = []
        if not SUPABASE_URL:
            missing.append("SUPABASE_URL")
        if not SUPABASE_SERVICE_ROLE_KEY:
            missing.append("SUPABASE_SERVICE_ROLE_KEY")
        if missing:
            joined = ", ".join(missing)
            raise RuntimeError(f"Supabase storage enabled but missing required env vars: {joined}")
        return SupabaseStorageBackend(
            url=SUPABASE_URL or "",
            bucket=SUPABASE_BUCKET,
            service_role_key=SUPABASE_SERVICE_ROLE_KEY or "",
        )
    # Local storage uses the structured projects directory for parity with Supabase layout
    return LocalStorageBackend(PROJECTS_DATA_DIR)


def get_storage() -> StorageBackend:
    return _storage_backend()


@lru_cache(maxsize=1)
def _auth_provider() -> AuthProvider:
    if AUTH_PROVIDER == "supabase":
        return SupabaseAuthProvider(url=SUPABASE_URL, anon_key=SUPABASE_ANON_KEY)
    return LocalAuthProvider()


def get_auth_provider() -> AuthProvider:
    return _auth_provider()

