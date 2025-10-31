"""Local username/password authentication provider."""

from __future__ import annotations

from uuid import UUID

from fastapi import Request, Response
from sqlalchemy.orm import Session

from server.core.config import (
    SESSION_COOKIE_MAX_AGE,
    SESSION_COOKIE_NAME,
    SESSION_COOKIE_SECURE,
)
from server.db import models
from server.security import PasswordService, SessionService

from .base import AuthError, AuthProvider, SessionUser


class LocalAuthProvider(AuthProvider):
    """Implements the existing cookie-based local authentication flow."""

    def __init__(self) -> None:
        self._passwords = PasswordService()
        self._sessions = SessionService()

    def register(self, email: str, password: str, db: Session) -> SessionUser:
        normalized = email.strip().lower()
        if not normalized:
            raise AuthError("Email is required")

        user = models.User(email=normalized, password_hash=self._passwords.hash(password))
        db.add(user)
        db.flush()
        return SessionUser(id=str(user.id), email=user.email)

    def authenticate(self, email: str, password: str, db: Session) -> SessionUser:
        normalized = email.strip().lower()
        user = db.query(models.User).filter(models.User.email == normalized).one_or_none()
        if not user or not self._passwords.verify(user.password_hash, password):
            raise AuthError("Invalid credentials")
        return SessionUser(id=str(user.id), email=user.email)

    def attach_to_response(self, response: Response, user: SessionUser) -> None:
        token = self._sessions.create(user.id)
        response.set_cookie(
            SESSION_COOKIE_NAME,
            token,
            httponly=True,
            max_age=SESSION_COOKIE_MAX_AGE,
            secure=SESSION_COOKIE_SECURE,
            samesite="lax",
        )

    def clear_from_response(self, response: Response) -> None:
        response.delete_cookie(SESSION_COOKIE_NAME)

    def current_user(self, request: Request, db: Session) -> SessionUser | None:
        token = request.cookies.get(SESSION_COOKIE_NAME)
        if not token:
            return None
        data = self._sessions.parse(token)
        if not data:
            return None
        user_id = data.get("user_id")
        if not user_id:
            return None
        try:
            uuid = UUID(user_id)
        except ValueError:
            return None
        user = db.get(models.User, uuid)
        if not user:
            return None
        return SessionUser(id=str(user.id), email=user.email)


