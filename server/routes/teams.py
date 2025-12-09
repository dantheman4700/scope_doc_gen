from __future__ import annotations

from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from ..db import models
from ..dependencies import db_session
from .auth import SessionUser, get_current_user

router = APIRouter(prefix="/teams", tags=["teams"])


class TeamBase(BaseModel):
    name: str = Field(..., max_length=200)


class TeamCreateRequest(TeamBase):
    pass


class TeamResponse(TeamBase):
    id: UUID
    owner_id: UUID

    class Config:
        from_attributes = True


class TeamMemberResponse(BaseModel):
    user_id: UUID
    role: str

    class Config:
        from_attributes = True


class TeamDetailResponse(TeamResponse):
    members: List[TeamMemberResponse]


@router.post("/", response_model=TeamResponse, status_code=status.HTTP_201_CREATED)
async def create_team(
    payload: TeamCreateRequest,
    db: Session = Depends(db_session),
    current_user: SessionUser = Depends(get_current_user),
) -> TeamResponse:
    team = models.Team(
        name=payload.name.strip(),
        owner_id=current_user.id,
    )
    db.add(team)

    # Add the owner as the first member
    team_member = models.TeamMember(
        team=team,
        user_id=current_user.id,
        role="admin",
    )
    db.add(team_member)

    db.commit()
    db.refresh(team)
    return TeamResponse.model_validate(team)


@router.get("/", response_model=List[TeamResponse])
async def list_teams(
    db: Session = Depends(db_session),
    current_user: SessionUser = Depends(get_current_user),
) -> List[TeamResponse]:
    user_teams = (
        db.query(models.Team)
        .join(models.TeamMember)
        .filter(models.TeamMember.user_id == current_user.id)
        .all()
    )
    return [TeamResponse.model_validate(team) for team in user_teams]


@router.get("/{team_id}", response_model=TeamDetailResponse)
async def get_team(
    team_id: UUID,
    db: Session = Depends(db_session),
    current_user: SessionUser = Depends(get_current_user),
) -> TeamDetailResponse:
    team = db.get(models.Team, team_id)
    if not team:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")

    # Check if user is a member of the team
    is_member = (
        db.query(models.TeamMember)
        .filter_by(team_id=team_id, user_id=current_user.id)
        .one_or_none()
    )
    if not is_member:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a team member")

    return TeamDetailResponse.model_validate(team)


# ---- Team Settings ----

class TeamSettings(BaseModel):
    """Team-level settings for scope generation defaults and prompts."""
    scope_prompt: Optional[str] = None
    pso_prompt: Optional[str] = None
    image_prompt: Optional[str] = None
    pso_image_prompt: Optional[str] = None
    enable_solution_image: bool = True  # Enabled by default
    enable_pso_image: bool = True
    scope_template_id: Optional[str] = "1GTrMfUm0fswd_OMc7HAvERSmJpiEsgw9nY6JMQOFvI4"  # Default Scope template
    pso_template_id: Optional[str] = "1q25z5wUxsvaFC1oVHZ8QlLXPIB0j0eWubKn_aFINjAo"  # Default PSO template
    vector_similar_limit: int = 3
    enable_oneshot_research: bool = True
    enable_oneshot_vector: bool = True
    research_mode_default: str = "quick"
    image_resolution: str = "4K"  # 1K, 2K, or 4K
    image_aspect_ratio: str = "auto"  # auto, 1:1, 16:9, 9:16, 4:3, 3:4

    class Config:
        extra = "ignore"


class TeamSettingsResponse(TeamSettings):
    team_id: UUID


def _get_team_for_user(db: Session, team_id: UUID, user_id: UUID) -> models.Team:
    """Helper to get a team and verify user membership."""
    team = db.get(models.Team, team_id)
    if not team:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")

    is_member = (
        db.query(models.TeamMember)
        .filter_by(team_id=team_id, user_id=user_id)
        .one_or_none()
    )
    if not is_member:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a team member")
    return team


@router.get("/{team_id}/settings", response_model=TeamSettingsResponse)
async def get_team_settings(
    team_id: UUID,
    db: Session = Depends(db_session),
    current_user: SessionUser = Depends(get_current_user),
) -> TeamSettingsResponse:
    """Get team settings."""
    team = _get_team_for_user(db, team_id, current_user.id)
    settings_data: Dict[str, Any] = team.settings or {}
    settings = TeamSettings(**settings_data)
    return TeamSettingsResponse(team_id=team.id, **settings.model_dump())


@router.put("/{team_id}/settings", response_model=TeamSettingsResponse)
async def update_team_settings(
    team_id: UUID,
    payload: TeamSettings,
    db: Session = Depends(db_session),
    current_user: SessionUser = Depends(get_current_user),
) -> TeamSettingsResponse:
    """Update team settings."""
    team = _get_team_for_user(db, team_id, current_user.id)
    merged = {**(team.settings or {}), **payload.model_dump(exclude_unset=True)}
    team.settings = merged
    flag_modified(team, "settings")
    db.add(team)
    db.commit()
    db.refresh(team)
    settings = TeamSettings(**team.settings)
    return TeamSettingsResponse(team_id=team.id, **settings.model_dump())


# ---- Roadmap (stored in team settings) ----

class RoadmapItem(BaseModel):
    """Single roadmap item."""
    text: str
    completed: bool = False


class RoadmapSection(BaseModel):
    """Roadmap category with items."""
    category: str
    items: List[RoadmapItem]


class RoadmapConfig(BaseModel):
    """Full roadmap configuration."""
    sections: List[RoadmapSection] = []


@router.get("/{team_id}/roadmap", response_model=RoadmapConfig)
async def get_team_roadmap(
    team_id: UUID,
    db: Session = Depends(db_session),
    current_user: SessionUser = Depends(get_current_user),
) -> RoadmapConfig:
    """Get the team's roadmap configuration."""
    team = _get_team_for_user(db, team_id, current_user.id)
    settings = team.settings or {}
    roadmap_data = settings.get("roadmap", {})
    return RoadmapConfig(**roadmap_data) if roadmap_data else RoadmapConfig(sections=[])


@router.put("/{team_id}/roadmap", response_model=RoadmapConfig)
async def update_team_roadmap(
    team_id: UUID,
    payload: RoadmapConfig,
    db: Session = Depends(db_session),
    current_user: SessionUser = Depends(get_current_user),
) -> RoadmapConfig:
    """Update the team's roadmap configuration. Admin only."""
    team = _get_team_for_user(db, team_id, current_user.id)
    
    # Check if user is admin
    membership = (
        db.query(models.TeamMember)
        .filter_by(team_id=team_id, user_id=current_user.id)
        .one_or_none()
    )
    if not membership or membership.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admins can edit roadmap")
    
    # Update roadmap in settings
    settings = team.settings or {}
    settings["roadmap"] = payload.model_dump()
    team.settings = settings
    flag_modified(team, "settings")
    db.add(team)
    db.commit()
    db.refresh(team)
    
    return payload
