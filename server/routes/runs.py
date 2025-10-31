"""Run management endpoints backed by the job registry."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy.orm import Session

from server.core.research import ResearchMode

from ..services import JobRegistry, RunOptions
from ..dependencies import db_session
from ..db import models


router = APIRouter(prefix="/projects/{project_id}/runs", tags=["runs"])
run_router = APIRouter(prefix="/runs", tags=["runs"])


class CreateRunRequest(BaseModel):
    run_mode: str = Field("full", pattern="^(full|fast)$")
    research_mode: ResearchMode = ResearchMode.QUICK
    force_resummarize: bool = False
    save_intermediate: bool = True
    interactive: bool = False
    project_identifier: Optional[str] = None
    instructions: Optional[str] = None
    enable_vector_store: bool = True
    enable_web_search: bool = True


class RunStatusResponse(BaseModel):
    id: UUID
    project_id: str
    status: str
    run_mode: str
    research_mode: str
    created_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    result_path: Optional[str] = None
    error: Optional[str] = None
    params: dict


class RunStepResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    run_id: UUID
    name: str
    status: str
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    logs: Optional[str] = None


def _registry(request: Request) -> JobRegistry:
    registry = getattr(request.app.state, "job_registry", None)
    if registry is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Job registry unavailable")
    return registry


@router.get("/", response_model=List[RunStatusResponse])
async def list_runs(project_id: str, request: Request) -> List[RunStatusResponse]:
    registry = _registry(request)
    jobs = registry.list_jobs(project_id)
    return [RunStatusResponse(**job.to_dict()) for job in jobs]


@router.post("/", response_model=RunStatusResponse, status_code=status.HTTP_201_CREATED)
async def create_run(project_id: str, payload: CreateRunRequest, request: Request) -> RunStatusResponse:
    registry = _registry(request)
    options = RunOptions(
        save_intermediate=payload.save_intermediate,
        interactive=payload.interactive,
        project_identifier=payload.project_identifier,
        run_mode=payload.run_mode,
        research_mode=payload.research_mode.value,
        force_resummarize=payload.force_resummarize,
        instructions_override=payload.instructions,
        enable_vector_store=payload.enable_vector_store,
        enable_web_search=payload.enable_web_search,
    )
    job = registry.create_job(project_id, options)
    return RunStatusResponse(**job.to_dict())


@router.get("/{run_id}", response_model=RunStatusResponse)
async def get_run(project_id: str, run_id: UUID, request: Request) -> RunStatusResponse:
    registry = _registry(request)
    job = registry.get_job(run_id)
    if job is None or job.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    return RunStatusResponse(**job.to_dict())


@run_router.get("/{run_id}", response_model=RunStatusResponse)
async def get_run_by_id(run_id: UUID, db: Session = Depends(db_session)) -> RunStatusResponse:
    run = db.get(models.Run, run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    return RunStatusResponse(
        id=run.id,
        project_id=str(run.project_id),
        status=run.status,
        run_mode=run.mode,
        research_mode=run.research_mode,
        created_at=run.created_at,
        started_at=run.started_at,
        finished_at=run.finished_at,
        result_path=run.result_path,
        error=run.error,
        params=run.params,
    )


@run_router.get("/{run_id}/steps", response_model=List[RunStepResponse])
async def get_run_steps(run_id: UUID, db: Session = Depends(db_session)) -> List[RunStepResponse]:
    run = db.get(models.Run, run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    steps = (
        db.query(models.RunStep)
        .filter(models.RunStep.run_id == run_id)
        .order_by(models.RunStep.started_at.asc())
        .all()
    )
    return [RunStepResponse.model_validate(step) for step in steps]


@run_router.get("/{run_id}/events")
async def stream_run_events(run_id: UUID) -> None:
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Run event stream not implemented yet")

