"""
API routes for Google OAuth user account connection.
Stores OAuth tokens per-user (not per-team).
"""

import logging
import secrets
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from server.db import models
from ..dependencies import db_session
from .auth import get_current_user
from server.services.google_user_oauth import (
    get_authorization_url,
    exchange_code_for_tokens,
    is_token_valid,
    revoke_tokens,
)

logger = logging.getLogger(__name__)

google_oauth_router = APIRouter(prefix="/google-oauth", tags=["google-oauth"])
# Alias for backwards compatibility with __init__.py
router = google_oauth_router


def get_user_team(user: models.User) -> Optional[models.Team]:
    """Get the user's first team via TeamMember relationship."""
    if user.teams:  # user.teams is List[TeamMember]
        return user.teams[0].team
    return None


def get_user_google_access_token(user_id: UUID, db: Session) -> Optional[str]:
    """
    Get the Google access token for a user from their personal settings.
    
    Args:
        user_id: The user's UUID
        db: Database session
        
    Returns:
        The access token string or None if not available
    """
    user = db.get(models.User, user_id)
    if not user:
        return None
    
    google_tokens = user.google_tokens or {}
    
    if not google_tokens or not is_token_valid(google_tokens):
        return None
    
    return google_tokens.get("access_token")


def get_user_google_tokens(user_id: UUID, db: Session) -> Optional[dict]:
    """
    Get the full Google token data for a user (for creating refreshable credentials).
    
    Args:
        user_id: The user's UUID
        db: Database session
        
    Returns:
        The token data dictionary or None if not available
    """
    user = db.get(models.User, user_id)
    if not user:
        return None
    
    google_tokens = user.google_tokens or {}
    
    if not google_tokens or not is_token_valid(google_tokens):
        return None
    
    return google_tokens


class GoogleConnectionStatus(BaseModel):
    connected: bool
    email: Optional[str] = None
    can_export: bool = False


class DisconnectResponse(BaseModel):
    success: bool
    message: str


@google_oauth_router.get("/status", response_model=GoogleConnectionStatus)
async def get_google_connection_status(
    user: models.User = Depends(get_current_user),
    db: Session = Depends(db_session),
):
    """Check if the current user has a connected Google account."""
    # user is a SessionUser pydantic model, fetch the actual DB model
    user_record = db.get(models.User, user.id)
    if not user_record:
        logger.warning(f"User {user.id} not found when checking Google status")
        return GoogleConnectionStatus(connected=False, can_export=False)
    
    google_tokens = user_record.google_tokens or {}
    logger.info(f"Checking Google status for user {user.id}: tokens present={bool(google_tokens)}, has_refresh={bool(google_tokens.get('refresh_token'))}")
    
    connected = is_token_valid(google_tokens)
    
    return GoogleConnectionStatus(
        connected=connected,
        email=google_tokens.get("email") if connected else None,
        can_export=connected,
    )


@google_oauth_router.get("/connect")
async def initiate_google_connection(
    user: models.User = Depends(get_current_user),
    db: Session = Depends(db_session),
):
    """
    Initiate Google OAuth flow.
    Returns the authorization URL to redirect the user to.
    """
    # Generate state parameter for CSRF protection
    state = f"{user.id}:{secrets.token_urlsafe(32)}"
    
    # Store state temporarily (in production, use Redis or similar)
    # For now, we'll encode the user ID in the state
    
    authorization_url, _ = get_authorization_url(state=state)
    
    return {"authorization_url": authorization_url}


@google_oauth_router.get("/callback")
async def google_oauth_callback(
    code: str = Query(...),
    state: str = Query(...),
    error: Optional[str] = Query(None),
    db: Session = Depends(db_session),
):
    """
    Handle Google OAuth callback.
    This endpoint is called by Google after user authorization.
    """
    if error:
        logger.error(f"Google OAuth error: {error}")
        # Redirect to settings with error
        return RedirectResponse(url="/settings?google_error=" + error)
    
    try:
        # Extract user ID from state
        user_id_str = state.split(":")[0]
        user_id = UUID(user_id_str)
    except (ValueError, IndexError):
        logger.error(f"Invalid state parameter: {state}")
        return RedirectResponse(url="/settings?google_error=invalid_state")
    
    # Get user
    user = db.get(models.User, user_id)
    if not user:
        return RedirectResponse(url="/settings?google_error=user_not_found")
    
    try:
        # Exchange code for tokens
        tokens = exchange_code_for_tokens(code)
        
        # Store tokens directly on the user record
        # Use flag_modified to ensure SQLAlchemy tracks the JSONB change
        user.google_tokens = tokens
        flag_modified(user, "google_tokens")
        db.add(user)  # Ensure the user is in the session
        db.commit()
        db.refresh(user)  # Refresh to confirm the change was persisted
        
        logger.info(f"Google tokens stored for user {user.id}, email: {tokens.get('email')}, has_refresh: {bool(tokens.get('refresh_token'))}")
        
        return RedirectResponse(url="/settings?google_connected=true")
        
    except Exception as e:
        logger.exception(f"Failed to exchange code for tokens: {e}")
        return RedirectResponse(url="/settings?google_error=token_exchange_failed")


@google_oauth_router.post("/disconnect", response_model=DisconnectResponse)
async def disconnect_google_account(
    user: models.User = Depends(get_current_user),
    db: Session = Depends(db_session),
):
    """Disconnect the user's Google account."""
    # Refresh user from database
    user_record = db.get(models.User, user.id)
    if not user_record:
        return DisconnectResponse(success=True, message="User not found")
    
    google_tokens = user_record.google_tokens
    
    if google_tokens:
        # Revoke tokens
        revoke_tokens(google_tokens)
        
        # Clear tokens from user record
        user_record.google_tokens = None
        db.commit()
        
        logger.info(f"Google account disconnected for user {user.id}")
    
    return DisconnectResponse(success=True, message="Google account disconnected")


# Secondary router for the legacy /google/oauth/callback endpoint
# that the frontend page.tsx posts to
legacy_google_oauth_router = APIRouter(prefix="/google/oauth", tags=["google-oauth"])


class OAuthCallbackRequest(BaseModel):
    code: str
    state: str


class OAuthCallbackResponse(BaseModel):
    connected: bool
    detail: Optional[str] = None


@legacy_google_oauth_router.post("/callback", response_model=OAuthCallbackResponse)
async def google_oauth_callback_post(
    payload: OAuthCallbackRequest,
    db: Session = Depends(db_session),
):
    """
    Handle Google OAuth callback via POST from frontend.
    This is called by the frontend page after Google redirects back.
    """
    try:
        # Extract user ID from state
        user_id_str = payload.state.split(":")[0]
        user_id = UUID(user_id_str)
    except (ValueError, IndexError):
        logger.error(f"Invalid state parameter: {payload.state}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid state parameter"
        )
    
    # Get user
    user = db.get(models.User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    try:
        # Exchange code for tokens
        tokens = exchange_code_for_tokens(payload.code)
        
        # Store tokens directly on the user record
        user.google_tokens = tokens
        db.commit()
        logger.info(f"Google tokens stored for user {user.id}")
        return OAuthCallbackResponse(connected=True)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to exchange code for tokens: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Token exchange failed: {str(e)}"
        )
