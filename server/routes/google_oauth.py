"""
API routes for Google OAuth user account connection.
"""

import logging
import secrets
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

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


def get_user_google_access_token(user_id: UUID, db: Session) -> Optional[str]:
    """
    Get the Google access token for a user from their team settings.
    
    Args:
        user_id: The user's UUID
        db: Database session
        
    Returns:
        The access token string or None if not available
    """
    user = db.get(models.User, user_id)
    if not user or not user.team_id:
        return None
    
    team = db.get(models.Team, user.team_id)
    if not team:
        return None
    
    settings = team.settings or {}
    google_tokens = settings.get("google_tokens")
    
    if not google_tokens or not is_token_valid(google_tokens):
        return None
    
    return google_tokens.get("access_token")


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
    # Get user's Google tokens from their settings
    user_record = db.get(models.User, user.id)
    if not user_record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    # Check if user has google_tokens in their profile
    google_tokens = getattr(user_record, "google_tokens", None) or {}
    
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
        
        # Store tokens in user record
        # We need to add a google_tokens column to the users table
        # For now, we'll store in the team settings
        if user.team_id:
            team = db.get(models.Team, user.team_id)
            if team:
                settings = team.settings or {}
                settings["google_tokens"] = tokens
                settings["google_connected_user_id"] = str(user.id)
                team.settings = settings
                db.commit()
                logger.info(f"Google tokens stored for team {team.id}")
        
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
    if not user.team_id:
        return DisconnectResponse(success=True, message="No Google account connected")
    
    team = db.get(models.Team, user.team_id)
    if not team:
        return DisconnectResponse(success=True, message="No Google account connected")
    
    settings = team.settings or {}
    google_tokens = settings.get("google_tokens")
    
    if google_tokens:
        # Revoke tokens
        revoke_tokens(google_tokens)
        
        # Remove from settings
        settings.pop("google_tokens", None)
        settings.pop("google_connected_user_id", None)
        team.settings = settings
        db.commit()
        
        logger.info(f"Google account disconnected for team {team.id}")
    
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
        
        # Store tokens in team settings
        if user.team_id:
            team = db.get(models.Team, user.team_id)
            if team:
                settings = team.settings or {}
                settings["google_tokens"] = tokens
                settings["google_connected_user_id"] = str(user.id)
                team.settings = settings
                db.commit()
                logger.info(f"Google tokens stored for team {team.id}")
                return OAuthCallbackResponse(connected=True)
        
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User has no team"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to exchange code for tokens: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Token exchange failed: {str(e)}"
        )
