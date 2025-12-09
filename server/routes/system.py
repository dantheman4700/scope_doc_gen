"""System and diagnostics endpoints."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Dict, List, Optional

from server.adapters.auth import AuthError
from server.adapters.storage import StorageError
from server.core.config import AUTH_PROVIDER, STORAGE_PROVIDER, SUPABASE_BUCKET, SUPABASE_URL, HISTORY_ENABLED
from server.routes.auth import get_current_user, SessionUser

from ..dependencies import get_auth_provider, get_storage, db_session
from sqlalchemy.orm import Session
from server.db import models

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/system", tags=["system"])

# Global roadmap file path
GLOBAL_ROADMAP_PATH = Path(__file__).parent.parent.parent / "data" / "global_roadmap.json"


class RoadmapItem(BaseModel):
    text: str
    completed: bool = False


class RoadmapSection(BaseModel):
    category: str
    items: List[RoadmapItem]


class RoadmapConfig(BaseModel):
    sections: List[RoadmapSection]


def get_global_roadmap() -> RoadmapConfig:
    """Load global roadmap from file."""
    if GLOBAL_ROADMAP_PATH.exists():
        try:
            data = json.loads(GLOBAL_ROADMAP_PATH.read_text())
            return RoadmapConfig(**data)
        except Exception as e:
            logger.warning(f"Failed to load global roadmap: {e}")
    return RoadmapConfig(sections=[])


def save_global_roadmap(config: RoadmapConfig) -> None:
    """Save global roadmap to file."""
    GLOBAL_ROADMAP_PATH.parent.mkdir(parents=True, exist_ok=True)
    GLOBAL_ROADMAP_PATH.write_text(json.dumps(config.model_dump(), indent=2))


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


@router.get("/config")
async def get_system_config() -> Dict[str, object]:
    """Return system configuration flags for the frontend."""
    return {
        "history_enabled": HISTORY_ENABLED,
    }


@router.get("/roadmap", response_model=RoadmapConfig)
async def get_roadmap(
    current_user: SessionUser = Depends(get_current_user),
) -> RoadmapConfig:
    """Get the global roadmap (shared across all teams)."""
    return get_global_roadmap()


@router.put("/roadmap", response_model=RoadmapConfig)
async def update_roadmap(
    payload: RoadmapConfig,
    current_user: SessionUser = Depends(get_current_user),
    db: Session = Depends(db_session),
) -> RoadmapConfig:
    """Update the global roadmap. Admin only."""
    # Check if user is admin in any team
    membership = (
        db.query(models.TeamMember)
        .filter_by(user_id=current_user.id, role="admin")
        .first()
    )
    if not membership:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admins can edit roadmap")
    
    save_global_roadmap(payload)
    logger.info(f"Global roadmap updated by user {current_user.id}")
    return payload

