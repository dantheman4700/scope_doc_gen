"""System and diagnostics endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from typing import Dict

from server.adapters.auth import AuthError
from server.adapters.storage import StorageError
from server.core.config import AUTH_PROVIDER, STORAGE_PROVIDER, SUPABASE_BUCKET, SUPABASE_URL

from ..dependencies import get_auth_provider, get_storage


router = APIRouter(prefix="/system", tags=["system"])


@router.get("/providers")
async def provider_status() -> Dict[str, Dict[str, object]]:
    """Report active auth/storage providers and basic health info."""

    info: Dict[str, Dict[str, object]] = {
        "auth": {"provider": AUTH_PROVIDER},
        "storage": {"provider": STORAGE_PROVIDER},
    }

    # Auth provider health
    try:
        auth_provider = get_auth_provider()
        info["auth"]["status"] = "ok"
        if AUTH_PROVIDER == "supabase":
            info["auth"]["url"] = SUPABASE_URL
    except AuthError as exc:
        info["auth"]["status"] = "error"
        info["auth"]["detail"] = str(exc)
    except Exception as exc:  # pragma: no cover - defensive
        info["auth"]["status"] = "error"
        info["auth"]["detail"] = str(exc)

    # Storage provider health
    try:
        storage = get_storage()
        if STORAGE_PROVIDER == "supabase":
            try:
                storage.list("")  # lightweight sanity check
            except StorageError as exc:
                info["storage"]["status"] = "error"
                info["storage"]["detail"] = str(exc)
            else:
                info["storage"]["status"] = "ok"
                info["storage"]["bucket"] = SUPABASE_BUCKET
        else:
            info["storage"]["status"] = "ok"
    except StorageError as exc:
        info["storage"]["status"] = "error"
        info["storage"]["detail"] = str(exc)
    except Exception as exc:  # pragma: no cover - defensive
        info["storage"]["status"] = "error"
        info["storage"]["detail"] = str(exc)

    return info


@router.get("/status", status_code=status.HTTP_204_NO_CONTENT)
async def noop() -> None:
    """Simple smoke endpoint that can be used by load balancers."""
    return None

