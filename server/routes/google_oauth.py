"""Google OAuth endpoints for connecting user accounts to Docs/Drive."""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from server.core.config import (
    GOOGLE_OAUTH_CLIENT_ID,
    GOOGLE_OAUTH_CLIENT_SECRET,
    GOOGLE_OAUTH_REDIRECT_URI,
    GOOGLE_OAUTH_SCOPES,
)

from ..db import models
from ..dependencies import db_session
from .auth import SessionUser, get_current_user


router = APIRouter(prefix="/google", tags=["google"])


class GoogleStatusResponse(BaseModel):
    connected: bool


class GoogleAuthUrlResponse(BaseModel):
    url: str


class GoogleCallbackRequest(BaseModel):
    code: str
    state: str


def _ensure_oauth_config() -> None:
    missing = []
    if not GOOGLE_OAUTH_CLIENT_ID:
        missing.append("GOOGLE_OAUTH_CLIENT_ID")
    if not GOOGLE_OAUTH_CLIENT_SECRET:
        missing.append("GOOGLE_OAUTH_CLIENT_SECRET")
    if not GOOGLE_OAUTH_REDIRECT_URI:
        missing.append("GOOGLE_OAUTH_REDIRECT_URI")
    if missing:
        joined = ", ".join(missing)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Google OAuth not configured: missing {joined}",
        )


def _build_oauth_url(state: str) -> str:
    params = {
        "client_id": GOOGLE_OAUTH_CLIENT_ID,
        "redirect_uri": GOOGLE_OAUTH_REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(GOOGLE_OAUTH_SCOPES),
        "access_type": "offline",
        "include_granted_scopes": "true",
        # Explicit consent prompt the first time to ensure we get a refresh token.
        "prompt": "consent",
        "state": state,
    }
    return "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)


@router.get("/status", response_model=GoogleStatusResponse)
async def google_status(
    current_user: SessionUser = Depends(get_current_user),
    db: Session = Depends(db_session),
) -> GoogleStatusResponse:
    """Return whether the current user has connected Google Drive."""

    record = db.get(models.GoogleAuth, current_user.id)
    connected = bool(record and record.refresh_token)
    return GoogleStatusResponse(connected=connected)


@router.get("/auth-url", response_model=GoogleAuthUrlResponse)
async def google_auth_url(
    current_user: SessionUser = Depends(get_current_user),
    db: Session = Depends(db_session),
) -> GoogleAuthUrlResponse:
    """Return a Google OAuth URL for the current user to connect their account."""

    _ensure_oauth_config()

    state = secrets.token_urlsafe(32)
    now = datetime.utcnow()

    record = db.get(models.GoogleAuth, current_user.id)
    if record is None:
        record = models.GoogleAuth(user_id=current_user.id)
        db.add(record)

    record.state = state
    record.state_created_at = now
    db.commit()

    return GoogleAuthUrlResponse(url=_build_oauth_url(state))


@router.post("/oauth/callback", response_model=GoogleStatusResponse)
async def google_oauth_callback(
    payload: GoogleCallbackRequest,
    request: Request,
    current_user: SessionUser = Depends(get_current_user),
    db: Session = Depends(db_session),
) -> GoogleStatusResponse:
    """Handle OAuth callback: exchange code for tokens and persist them."""

    _ensure_oauth_config()

    record = db.get(models.GoogleAuth, current_user.id)
    if record is None or not record.state:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="OAuth state not found")

    # Basic CSRF/state validation with a short TTL window.
    if payload.state != record.state:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OAuth state")
    if record.state_created_at and record.state_created_at < datetime.utcnow() - timedelta(minutes=10):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="OAuth state has expired")

    # Clear state immediately to prevent replay even if token exchange fails.
    record.state = None
    record.state_created_at = None
    db.commit()

    data = {
        "client_id": GOOGLE_OAUTH_CLIENT_ID or "",
        "client_secret": GOOGLE_OAUTH_CLIENT_SECRET or "",
        "code": payload.code,
        "grant_type": "authorization_code",
        "redirect_uri": GOOGLE_OAUTH_REDIRECT_URI or "",
    }

    try:
        token_resp = httpx.post("https://oauth2.googleapis.com/token", data=data, timeout=15)
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to contact Google token endpoint: {exc}",
        )

    if token_resp.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Google token exchange failed ({token_resp.status_code})",
        )

    token_data = token_resp.json()
    access_token = token_data.get("access_token")
    refresh_token = token_data.get("refresh_token") or record.refresh_token
    expires_in = token_data.get("expires_in")
    scope = token_data.get("scope")

    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Google token exchange did not return an access token",
        )

    # Persist tokens
    record.access_token = access_token
    record.refresh_token = refresh_token
    record.scope = scope
    if expires_in:
        record.token_expiry = datetime.utcnow() + timedelta(seconds=int(expires_in))
    else:
        record.token_expiry = None

    db.add(record)
    db.commit()

    return GoogleStatusResponse(connected=bool(record.refresh_token))


def get_user_google_access_token(
    user_id,
    db: Session,
) -> str:
    """
    Helper used by other routes to obtain a fresh access token for the user.

    Performs a refresh using the stored refresh token when necessary and updates
    the database accordingly.
    """

    _ensure_oauth_config()

    record = db.get(models.GoogleAuth, user_id)
    if record is None or not record.refresh_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google account not connected",
        )

    now = datetime.utcnow()
    if record.access_token and record.token_expiry and record.token_expiry > now + timedelta(seconds=60):
        return record.access_token

    data = {
        "client_id": GOOGLE_OAUTH_CLIENT_ID or "",
        "client_secret": GOOGLE_OAUTH_CLIENT_SECRET or "",
        "grant_type": "refresh_token",
        "refresh_token": record.refresh_token,
    }

    try:
        token_resp = httpx.post("https://oauth2.googleapis.com/token", data=data, timeout=15)
        token_resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to refresh Google access token: {exc.response.status_code}",
        )
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to refresh Google access token: {exc}",
        )

    token_data = token_resp.json()
    access_token = token_data.get("access_token")
    expires_in = token_data.get("expires_in")

    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Google token refresh did not return an access token",
        )

    record.access_token = access_token
    if expires_in:
        record.token_expiry = datetime.utcnow() + timedelta(seconds=int(expires_in))
    else:
        record.token_expiry = None
    db.add(record)
    db.commit()

    return access_token


