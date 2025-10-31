"""Authentication endpoints for the dashboard."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from ..adapters.auth import AuthError, AuthUnsupportedError, SessionUser as ProviderUser
from ..db import models
from ..dependencies import db_session, get_auth_provider


router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


class SessionUser(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str


def _normalise_email(value: str) -> str:
    return value.strip().lower()


def _to_response_model(user: ProviderUser) -> SessionUser:
    return SessionUser.model_validate({"id": user.id, "email": user.email})


@router.post("/register", response_model=SessionUser)
async def register_admin(payload: RegisterRequest, db: Session = Depends(db_session)) -> SessionUser:
    provider = get_auth_provider()

    from ..db import models  # local import to avoid circular dependency when unavailable

    existing = db.query(models.User).count()
    if existing > 0:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Registration disabled after initial setup")

    try:
        user = provider.register(_normalise_email(payload.email), payload.password, db)
    except AuthUnsupportedError:
        raise HTTPException(status_code=status.HTTP_405_METHOD_NOT_ALLOWED, detail="Registration managed externally")
    except AuthError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    return _to_response_model(user)


@router.post("/login", response_model=SessionUser)
async def login(payload: LoginRequest, response: Response, db: Session = Depends(db_session)) -> SessionUser:
    provider = get_auth_provider()
    try:
        user = provider.authenticate(_normalise_email(payload.email), payload.password, db)
        provider.attach_to_response(response, user)
    except AuthUnsupportedError:
        raise HTTPException(status_code=status.HTTP_405_METHOD_NOT_ALLOWED, detail="Login managed externally")
    except AuthError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))

    return _to_response_model(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response) -> None:
    provider = get_auth_provider()
    try:
        provider.clear_from_response(response)
    except AuthUnsupportedError:
        # Supabase handles logout on the client; nothing to do server-side.
        return


def get_current_user(
    request: Request,
    db: Session = Depends(db_session),
) -> SessionUser:
    provider = get_auth_provider()
    try:
        user = provider.current_user(request, db)
    except AuthError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return _to_response_model(user)


@router.get("/me", response_model=SessionUser)
async def me(current_user: SessionUser = Depends(get_current_user)) -> SessionUser:
    return current_user

