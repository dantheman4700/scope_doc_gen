"""Project CRUD endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy.orm import Session, joinedload

from server.core.config import DATA_ROOT

from ..dependencies import db_session
from ..db import models
from ..storage.projects import ensure_project_structure
from .auth import get_current_user, SessionUser


router = APIRouter(prefix="/projects", tags=["projects"])


class ProjectBase(BaseModel):
    name: str = Field(..., max_length=200)
    description: Optional[str] = None
    flags: dict = Field(default_factory=dict)


class ProjectCreateRequest(ProjectBase):
    team_id: Optional[UUID] = None


class ProjectUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = None
    flags: Optional[dict] = None


class UserSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    email: str


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: Optional[str] = None
    flags: dict
    owner: Optional[UserSummaryResponse] = None
    team_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime


def _get_project(session: Session, project_id: UUID) -> models.Project:
    project = (
        session.query(models.Project)
        .options(joinedload(models.Project.owner))
        .filter(models.Project.id == project_id)
        .one_or_none()
    )
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


@router.get("/", response_model=List[ProjectResponse])
async def list_projects(
    db: Session = Depends(db_session),
    current_user: SessionUser = Depends(get_current_user),
) -> List[ProjectResponse]:
    user_teams = (
        db.query(models.TeamMember.team_id)
        .filter(models.TeamMember.user_id == current_user.id)
        .all()
    )
    team_ids = [team.team_id for team in user_teams]

    projects = (
        db.query(models.Project)
        .options(joinedload(models.Project.owner))
        .filter(
            (models.Project.owner_id == current_user.id) |
            (models.Project.team_id.in_(team_ids))
        )
        .order_by(models.Project.created_at.desc())
        .all()
    )
    return [ProjectResponse.model_validate(project) for project in projects]


@router.post("/", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: ProjectCreateRequest,
    db: Session = Depends(db_session),
    current_user: SessionUser = Depends(get_current_user),
) -> ProjectResponse:
    project = models.Project(
        name=payload.name.strip(),
        description=payload.description,
        flags=payload.flags or {},
        owner_id=current_user.id,
        team_id=payload.team_id,
    )
    db.add(project)
    db.commit()
    db.refresh(project)

    ensure_project_structure(DATA_ROOT, str(project.id))
    return ProjectResponse.model_validate(project)


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: UUID, db: Session = Depends(db_session)) -> ProjectResponse:
    project = _get_project(db, project_id)
    return ProjectResponse.model_validate(project)


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: UUID,
    payload: ProjectUpdateRequest,
    db: Session = Depends(db_session),
    _: SessionUser = Depends(get_current_user),
) -> ProjectResponse:
    project = _get_project(db, project_id)

    if payload.name is not None:
        project.name = payload.name.strip()
    if payload.description is not None:
        project.description = payload.description
    if payload.flags is not None:
        project.flags = payload.flags

    project.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(project)
    return ProjectResponse.model_validate(project)

