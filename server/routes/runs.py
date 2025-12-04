"""Run management endpoints backed by the job registry."""

from __future__ import annotations

import io
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy.orm import Session

from server.core.research import ResearchMode
from server.core.config import DATA_ROOT, HISTORY_EMBEDDING_MODEL
from server.core.history_profiles import ProfileEmbedder
from server.core.markdown_to_docx import markdown_to_docx_bytes

from ..services import JobRegistry, RunOptions
from ..dependencies import db_session, get_storage
from ..db import models
from ..storage.projects import ensure_project_structure
from ..adapters.storage import StorageBackend


router = APIRouter(prefix="/projects/{project_id}/runs", tags=["runs"])
run_router = APIRouter(prefix="/runs", tags=["runs"])


class CreateRunRequest(BaseModel):
    run_mode: str = Field("full", pattern="^(full|fast)$")
    research_mode: ResearchMode = ResearchMode.QUICK
    interactive: bool = False
    project_identifier: Optional[str] = None
    instructions: Optional[str] = None
    enable_vector_store: bool = True
    enable_web_search: bool = True
    included_file_ids: List[UUID] = Field(default_factory=list)
    parent_run_id: Optional[UUID] = None
    what_to_change: Optional[str] = None


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
    instructions: Optional[str] = None
    included_file_ids: List[str] = Field(default_factory=list)
    parent_run_id: Optional[str] = None
    extracted_variables_artifact_id: Optional[UUID] = None


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


def _storage_key(project_id: str, relative_path: str) -> str:
    clean = relative_path.replace("\\", "/").lstrip("/")
    return f"projects/{project_id}/{clean}"


async def _ensure_artifact_local(
    project_id: str,
    artifact: models.Artifact,
    storage: StorageBackend,
) -> Path:
    paths = ensure_project_structure(DATA_ROOT, project_id)
    local_path = (paths.root / artifact.path).resolve()
    local_path.parent.mkdir(parents=True, exist_ok=True)

    if not local_path.exists():
        storage_key = _storage_key(project_id, artifact.path)
        await run_in_threadpool(storage.download_to_path, storage_key, local_path)

    return local_path

 


def _job_to_response(job: JobStatus) -> RunStatusResponse:
    data = job.to_dict()
    params = data.get("params", {}) or {}
    data["instructions"] = params.get("instructions_override")
    data["included_file_ids"] = params.get("included_file_ids", [])
    data["parent_run_id"] = params.get("parent_run_id")
    data["extracted_variables_artifact_id"] = params.get("extracted_variables_artifact_id")
    return RunStatusResponse(**data)


def _db_run_to_response(run: models.Run) -> RunStatusResponse:
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
        params=run.params or {},
        instructions=run.instructions,
        included_file_ids=run.included_file_ids or [],
        parent_run_id=str(run.parent_run_id) if run.parent_run_id else None,
        extracted_variables_artifact_id=run.extracted_variables_artifact_id,
    )


@router.get("/", response_model=List[RunStatusResponse])
async def list_runs(
    project_id: str,
    request: Request,
    db: Session = Depends(db_session),
) -> List[RunStatusResponse]:
    registry = _registry(request)
    jobs = registry.list_jobs(project_id)
    job_map: dict[UUID, JobStatus] = {job.id: job for job in jobs}

    try:
        project_uuid = UUID(project_id)
    except ValueError:
        project_uuid = None

    responses: List[RunStatusResponse] = []

    if project_uuid is not None:
        db_runs = (
            db.query(models.Run)
            .filter(models.Run.project_id == project_uuid)
            .order_by(models.Run.created_at.desc())
            .all()
        )
        for run in db_runs:
            response = _db_run_to_response(run)
            job = job_map.pop(run.id, None)
            if job is not None:
                live = _job_to_response(job)
                response.status = live.status
                response.started_at = live.started_at or response.started_at
                response.finished_at = live.finished_at or response.finished_at
                response.result_path = live.result_path or response.result_path
                response.error = live.error or response.error
                response.params = live.params or response.params
                response.instructions = live.instructions or response.instructions
                response.included_file_ids = live.included_file_ids or response.included_file_ids
                response.parent_run_id = live.parent_run_id or response.parent_run_id
                response.extracted_variables_artifact_id = (
                    live.extracted_variables_artifact_id or response.extracted_variables_artifact_id
                )
            responses.append(response)

    # Include any remaining in-memory jobs (e.g., very new jobs not yet persisted)
    for job in job_map.values():
        responses.append(_job_to_response(job))

    # Sort by created_at desc for stable ordering
    responses.sort(key=lambda r: r.created_at, reverse=True)
    return responses


@router.post("/", response_model=RunStatusResponse, status_code=status.HTTP_201_CREATED)
async def create_run(project_id: str, payload: CreateRunRequest, request: Request) -> RunStatusResponse:
    registry = _registry(request)
    included_ids = [str(file_id) for file_id in payload.included_file_ids]
    parent_run_id = str(payload.parent_run_id) if payload.parent_run_id else None
    run_mode = payload.run_mode
    if parent_run_id:
        run_mode = "fast"
    options = RunOptions(
        interactive=payload.interactive,
        project_identifier=payload.project_identifier,
        run_mode=run_mode,
        research_mode=payload.research_mode.value,
        instructions_override=payload.instructions,
        enable_vector_store=payload.enable_vector_store,
        enable_web_search=payload.enable_web_search,
        included_file_ids=included_ids,
        parent_run_id=parent_run_id,
        variables_delta=payload.what_to_change,
    )
    job = registry.create_job(project_id, options)
    data = job.to_dict()
    params = data.get("params", {}) or {}
    data["instructions"] = params.get("instructions_override")
    data["included_file_ids"] = params.get("included_file_ids", [])
    data["parent_run_id"] = params.get("parent_run_id")
    data["extracted_variables_artifact_id"] = params.get("extracted_variables_artifact_id")
    return RunStatusResponse(**data)


@router.get("/{run_id}", response_model=RunStatusResponse)
async def get_run(
    project_id: str,
    run_id: UUID,
    request: Request,
    db: Session = Depends(db_session),
) -> RunStatusResponse:
    registry = _registry(request)
    job = registry.get_job(run_id)
    if job is not None and job.project_id == project_id:
        return _job_to_response(job)

    run = db.get(models.Run, run_id)
    if run is not None and str(run.project_id) == project_id:
        return _db_run_to_response(run)

        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")


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
        instructions=run.instructions,
        included_file_ids=run.included_file_ids or [],
        parent_run_id=str(run.parent_run_id) if run.parent_run_id else None,
        extracted_variables_artifact_id=run.extracted_variables_artifact_id,
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


@run_router.post("/{run_id}/embed", status_code=status.HTTP_201_CREATED)
async def embed_run_output(
    run_id: UUID,
    request: Request,
    db: Session = Depends(db_session),
    storage: StorageBackend = Depends(get_storage),
):
    """
    Create a compact profile embedding for a run using its extracted variables.
    This mirrors the import system for consistent similarity matching.
    """
    vector_store = getattr(request.app.state, "vector_store", None)
    if vector_store is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Vector store unavailable")

    run = db.get(models.Run, run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    if run.status != "success":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Run must be successful before embedding")

    # Find the extracted variables artifact
    variables_artifact = (
        db.query(models.Artifact)
        .filter(models.Artifact.run_id == run_id, models.Artifact.kind == "variables")
        .order_by(models.Artifact.created_at.desc())
        .first()
    )

    if variables_artifact is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No extracted variables available for embedding")

    project_uuid = None
    project_id_str = str(run.project_id)
    try:
        project_uuid = UUID(project_id_str)
    except Exception:
        project_uuid = None

    # Load the extracted variables
    try:
        local_path = await _ensure_artifact_local(project_id_str, variables_artifact, storage)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to download variables: {exc}")

    if not local_path.exists() or not local_path.is_file():
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Variables artifact is unavailable")

    try:
        import json
        with open(local_path, 'r', encoding='utf-8') as f:
            variables = json.load(f)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to parse variables: {exc}")

    # Build compact profile text (same as import system)
    try:
        from server.core.history_profiles import build_profile_text
        profile_text = build_profile_text(
            title=variables.get("project_name"),
            variables=variables,
            services=variables.get("services"),
            tags=variables.get("tags"),
        )
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to build profile: {exc}")

    # Generate embedding from compact profile
    try:
        embedder = ProfileEmbedder(HISTORY_EMBEDDING_MODEL)
        embedding = list(embedder.embed(profile_text))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Embedding generation failed: {exc}")

    # Store full variables in metadata for reference
    metadata = {
        "project_id": project_id_str,
        "run_id": str(run.id),
        "mode": run.mode,
        "research_mode": run.research_mode,
        "result_path": run.result_path,
        "profile_text": profile_text,
        "title": variables.get("project_name"),
        "hours_total": variables.get("hours_total"),
        "timeline_weeks": variables.get("timeline_weeks"),
        "milestone_count": len(variables.get("milestones", [])),
        "services": variables.get("services"),
        "tags": variables.get("tags"),
        "dev_hours": variables.get("dev_hours"),
        "training_hours": variables.get("training_hours"),
        "pm_hours": variables.get("pm_hours"),
        "total_setup_cost": variables.get("total_setup_cost"),
        "monthly_operating_cost": variables.get("monthly_operating_cost"),
        "automation_outputs": variables.get("automation_outputs"),
        "client_name": variables.get("client_name"),
        "project_name": variables.get("project_name"),
        "industry": variables.get("industry"),
        "project_type": variables.get("project_type"),
    }
    if run.instructions:
        metadata["instructions"] = run.instructions

    try:
        embedding_id = vector_store.upsert_embedding(
            embedding=embedding,
            project_id=project_uuid,
            doc_kind="rendered_scope",
            metadata=metadata,
        )
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to store embedding: {exc}")

    return {"embedding_id": str(embedding_id), "profile_text": profile_text}


@run_router.get("/{run_id}/download-docx")
async def download_run_docx(
    run_id: UUID,
    db: Session = Depends(db_session),
    storage: StorageBackend = Depends(get_storage),
):
    run = db.get(models.Run, run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    if run.status != "success":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Run must be successful before exporting")

    artifact = (
        db.query(models.Artifact)
        .filter(models.Artifact.run_id == run_id, models.Artifact.kind == "rendered_doc")
        .order_by(models.Artifact.created_at.desc())
        .first()
    )

    if artifact is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Rendered document not found")

    project_id_str = str(run.project_id)

    try:
        local_path = await _ensure_artifact_local(project_id_str, artifact, storage)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to download artifact: {exc}")

    if not local_path.exists() or not local_path.is_file():
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Rendered document is unavailable")

    try:
        content = local_path.read_text(encoding="utf-8")
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to read artifact: {exc}")

    buffer = markdown_to_docx_bytes(content)
    filename_stem = Path(artifact.path).stem or f"run-{run.id}"
    docx_filename = f"{filename_stem}.docx"

    headers = {
        "Content-Disposition": f'attachment; filename="{docx_filename}"'
    }
    media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    return StreamingResponse(buffer, media_type=media_type, headers=headers)


@run_router.get("/{run_id}/download-md")
async def download_run_md(
    run_id: UUID,
    db: Session = Depends(db_session),
    storage: StorageBackend = Depends(get_storage),
):
    run = db.get(models.Run, run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    if run.status != "success":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Run must be successful before exporting")

    artifact = (
        db.query(models.Artifact)
        .filter(models.Artifact.run_id == run_id, models.Artifact.kind == "rendered_doc")
        .order_by(models.Artifact.created_at.desc())
        .first()
    )

    if artifact is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Rendered document not found")

    project_id_str = str(run.project_id)

    try:
        local_path = await _ensure_artifact_local(project_id_str, artifact, storage)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to download artifact: {exc}")

    if not local_path.exists() or not local_path.is_file():
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Rendered document is unavailable")

    try:
        data = local_path.read_bytes()
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to read artifact: {exc}")

    filename = Path(artifact.path).name or f"run-{run.id}.md"
    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"'
    }
    media_type = "text/markdown; charset=utf-8"
    return StreamingResponse(io.BytesIO(data), media_type=media_type, headers=headers)

