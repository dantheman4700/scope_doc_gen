"""Supabase JWT-backed authentication provider."""

from __future__ import annotations

import time
from typing import Dict, Tuple
from uuid import UUID

import httpx
from fastapi import Request, Response
from sqlalchemy.orm import Session

from server.core.config import SUPABASE_ANON_KEY, SUPABASE_URL
from server.db import models

from .base import AuthError, AuthProvider, AuthUnsupportedError, SessionUser


# Cache verified tokens for 5 minutes to avoid hitting Supabase API on every request
_TOKEN_CACHE: Dict[str, Tuple[dict, float]] = {}
_TOKEN_CACHE_TTL = 300  # 5 minutes


def _extract_bearer_token(request: Request) -> str | None:
    header = request.headers.get("authorization")
    if header and header.lower().startswith("bearer "):
        return header.split(" ", 1)[1]
    cookie_token = request.cookies.get("sb-access-token")
    if cookie_token:
        return cookie_token
    return None


class SupabaseAuthProvider(AuthProvider):
    """Delegates authentication to Supabase Auth via access tokens."""

    def __init__(self, *, url: str | None = None, anon_key: str | None = None) -> None:
        supabase_url = url or SUPABASE_URL
        supabase_anon = anon_key or SUPABASE_ANON_KEY
        if not supabase_url or not supabase_anon:
            raise AuthError("Supabase credentials are not configured")

        self._client = httpx.Client(
            base_url=f"{supabase_url.rstrip('/')}/auth/v1",
            headers={"apikey": supabase_anon},
            timeout=10.0,
        )

    # Registration and direct login handled by Supabase
    def register(self, email: str, password: str, db: Session) -> SessionUser:  # pragma: no cover - explicit override
        raise AuthUnsupportedError("Registration is managed by Supabase")

    def authenticate(self, email: str, password: str, db: Session) -> SessionUser:  # pragma: no cover
        raise AuthUnsupportedError("Login is managed by Supabase")

    def attach_to_response(self, response: Response, user: SessionUser) -> None:  # pragma: no cover
        raise AuthUnsupportedError("Sessions are managed by Supabase")

    def clear_from_response(self, response: Response) -> None:
        # Supabase clients handle logout by revoking tokens; nothing to clear server-side.
        return None

    def current_user(self, request: Request, db: Session) -> SessionUser | None:
        token = _extract_bearer_token(request)
        if not token:
            return None

        # Check cache first to avoid hitting Supabase API on every request
        now = time.time()
        if token in _TOKEN_CACHE:
            cached_data, cached_time = _TOKEN_CACHE[token]
            if now - cached_time < _TOKEN_CACHE_TTL:
                # Use cached data
                data = cached_data
            else:
                # Cache expired, remove it
                del _TOKEN_CACHE[token]
                data = None
        else:
            data = None

        # If not cached or expired, verify with Supabase
        if data is None:
            try:
                response = self._client.get("/user", headers={"authorization": f"Bearer {token}"})
            except httpx.HTTPError as exc:  # pragma: no cover - network failure
                raise AuthError(f"Supabase request failed: {exc}") from exc

            if response.status_code >= 400:
                return None

            data = response.json()
            # Cache the result
            _TOKEN_CACHE[token] = (data, now)
            
            # Clean up old cache entries periodically (keep cache size manageable)
            if len(_TOKEN_CACHE) > 100:
                expired = [k for k, (_, t) in _TOKEN_CACHE.items() if now - t >= _TOKEN_CACHE_TTL]
                for k in expired:
                    del _TOKEN_CACHE[k]

        user_id = data.get("id")
        email = data.get("email")
        if not email or not user_id:
            return None

        try:
            uuid = UUID(user_id)
        except ValueError:
            raise AuthError("Supabase returned invalid user id")

        user = db.get(models.User, uuid)
        if not user:
            user = db.query(models.User).filter(models.User.email == email).one_or_none()
        if not user:
            user = models.User(id=uuid, email=email, password_hash="supabase")
            db.add(user)
            db.flush()

        return SessionUser(id=str(user.id), email=user.email)


