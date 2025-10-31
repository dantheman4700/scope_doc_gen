"""Base authentication provider definitions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from fastapi import Request, Response
from sqlalchemy.orm import Session


@dataclass
class SessionUser:
    id: str
    email: str


class AuthError(RuntimeError):
    """Raised when an authentication operation fails."""


class AuthUnsupportedError(AuthError):
    """Raised when an operation is not supported by the provider."""


class AuthProvider:
    """Abstract base for authentication providers."""

    def register(self, email: str, password: str, db: Session) -> SessionUser:
        raise AuthUnsupportedError("Registration not supported")

    def authenticate(self, email: str, password: str, db: Session) -> SessionUser:
        raise AuthUnsupportedError("Login not supported")

    def attach_to_response(self, response: Response, user: SessionUser) -> None:
        raise AuthUnsupportedError("Sessions not supported")

    def clear_from_response(self, response: Response) -> None:
        raise AuthUnsupportedError("Sessions not supported")

    def current_user(self, request: Request, db: Session) -> Optional[SessionUser]:
        raise AuthError("Unable to resolve current user")


