"""Run management endpoints backed by the job registry."""

from __future__ import annotations

import asyncio
import io
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy.orm import Session

from server.core.research import ResearchMode
from server.core.config import (
    DATA_ROOT,
    HISTORY_EMBEDDING_MODEL,
    GOOGLE_OAUTH_SCOPES,
    GOOGLE_SERVICE_ACCOUNT_FILE,
    GOOGLE_TEMPLATE_FOLDER_ID,
)
from server.core.history_profiles import ProfileEmbedder
from server.core.markdown_to_docx import markdown_to_docx_bytes

from ..services import JobRegistry, RunOptions
from ..services.google_drive_templates import GoogleDriveTemplateService
from ..dependencies import db_session, get_storage
from ..db import models
from ..storage.projects import ensure_project_structure
from ..adapters.storage import StorageBackend
from .auth import SessionUser, get_current_user
from .google_oauth import get_user_google_access_token, get_user_google_tokens
from server.services.google_user_oauth import credentials_from_tokens


router = APIRouter(prefix="/projects/{project_id}/runs", tags=["runs"])
run_router = APIRouter(prefix="/runs", tags=["runs"])

logger = logging.getLogger(__name__)


class TemplateResponse(BaseModel):
    id: str
    name: str
    mimeType: str
    webViewLink: str


class CreateRunRequest(BaseModel):
    run_mode: str = Field("full", pattern="^(full|fast|oneshot)$")
    research_mode: ResearchMode = ResearchMode.QUICK
    interactive: bool = False
    project_identifier: Optional[str] = None
    instructions: Optional[str] = None
    enable_vector_store: bool = True
    enable_web_search: bool = True
    included_file_ids: List[UUID] = Field(default_factory=list)
    parent_run_id: Optional[UUID] = None
    what_to_change: Optional[str] = None
    template_id: Optional[str] = None  # Google Drive file ID for one-shot mode templates
    template_type: Optional[str] = None  # "Scope" or "PSO" - document type


class RunStatusResponse(BaseModel):
    id: UUID
    project_id: str
    status: str
    run_mode: str
    research_mode: str
    template_type: Optional[str] = None
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
    feedback: Optional[dict] = None
    google_doc_url: Optional[str] = None
    google_doc_id: Optional[str] = None
    document_title: Optional[str] = None  # Extracted H1 from markdown
    questions_state: Optional[Dict[str, Any]] = None  # Persisted questions answers and lock state
    is_indexed: bool = False  # Whether the workspace has been indexed for search
    indexed_chunks: int = 0  # Number of indexed chunks


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


def _create_step(db: Session, run_id: UUID, name: str, status_str: str = "running") -> models.RunStep:
    """Create a new step record for the given run."""
    from uuid import uuid4
    from datetime import datetime as dt
    step = models.RunStep(
        id=uuid4(),
        run_id=run_id,
        name=name,
        status=status_str,
        started_at=dt.utcnow(),
    )
    db.add(step)
    db.commit()
    db.refresh(step)
    return step


def _finish_step(db: Session, step: models.RunStep, status_str: str = "success", logs: str = None):
    """Mark a step as finished."""
    from datetime import datetime as dt
    step.status = status_str
    step.finished_at = dt.utcnow()
    if logs:
        step.logs = logs
    db.add(step)
    db.commit()


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
    data["feedback"] = params.get("feedback")
    data["template_type"] = params.get("template_type")
    return RunStatusResponse(**data)


def _extract_document_title(artifact_path: Optional[str], project_id: str) -> Optional[str]:
    """Extract the H1 title from a markdown document."""
    if not artifact_path:
        return None
    try:
        # Build the full path
        full_path = Path(DATA_ROOT) / "projects" / project_id / artifact_path
        if not full_path.exists():
            # Try the path as-is
            full_path = Path(artifact_path)
        if not full_path.exists():
            return None
        
        # Read first 2000 chars to find the title
        content = full_path.read_text(encoding="utf-8")[:2000]
        
        # Look for H1 (# Title) at the start of a line
        import re
        h1_match = re.search(r'^#\s+(.+?)$', content, re.MULTILINE)
        if h1_match:
            title = h1_match.group(1).strip()
            # Clean up any markdown formatting
            title = re.sub(r'\*\*(.+?)\*\*', r'\1', title)  # Bold
            title = re.sub(r'\*(.+?)\*', r'\1', title)  # Italic
            return title[:100]  # Limit length
        
        return None
    except Exception:
        return None


def _db_run_to_response(run: models.Run, db: Optional[Session] = None) -> RunStatusResponse:
    # Try to get google doc URL from the rendered_doc artifact
    google_doc_url = None
    google_doc_id = None
    document_title = None
    artifact = None
    is_indexed = False
    indexed_chunks = 0

    if db and run.status == "success":
        artifact = (
            db.query(models.Artifact)
            .filter(models.Artifact.run_id == run.id, models.Artifact.kind == "rendered_doc")
            .order_by(models.Artifact.created_at.desc())
            .first()
        )
        if artifact:
            if artifact.meta:
                google_doc_url = artifact.meta.get("google_doc_url")
                google_doc_id = artifact.meta.get("google_doc_id")
            # Extract document title from markdown H1
            document_title = _extract_document_title(artifact.path, str(run.project_id))
        
        # Check indexing status
        try:
            from server.db.session import engine
            from server.services.vector_store import VectorStore
            vector_store = VectorStore(engine)
            indexed_chunks = vector_store.count_run_embeddings(run.id)
            is_indexed = indexed_chunks > 0
        except Exception:
            pass  # Silently ignore indexing status errors
    
    # Extract questions state from params
    questions_state = (run.params or {}).get("questions_state")
    
    return RunStatusResponse(
        id=run.id,
        project_id=str(run.project_id),
        status=run.status,
        run_mode=run.mode,
        research_mode=run.research_mode,
        template_type=run.template_type,
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
        feedback=(run.params or {}).get("feedback"),
        google_doc_url=google_doc_url,
        google_doc_id=google_doc_id,
        document_title=document_title,
        questions_state=questions_state,
        is_indexed=is_indexed,
        indexed_chunks=indexed_chunks,
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
            response = _db_run_to_response(run, db)
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


@router.get("/templates", response_model=List[TemplateResponse])
async def list_templates() -> List[TemplateResponse]:
    """
    List available templates from Google Drive folder for one-shot mode.
    """
    if not GOOGLE_SERVICE_ACCOUNT_FILE:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google Drive template service not configured (GOOGLE_SERVICE_ACCOUNT_FILE not set)",
        )

    try:
        template_service = GoogleDriveTemplateService(
            service_account_file=GOOGLE_SERVICE_ACCOUNT_FILE,
            folder_id=GOOGLE_TEMPLATE_FOLDER_ID,
        )
        templates = template_service.list_templates()
        return [TemplateResponse(**t) for t in templates]
    except Exception as exc:
        logger.exception("Failed to list templates from Google Drive")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to list templates: {str(exc)}",
        )


@router.post("/", response_model=RunStatusResponse, status_code=status.HTTP_201_CREATED)
async def create_run(project_id: str, payload: CreateRunRequest, request: Request) -> RunStatusResponse:
    registry = _registry(request)
    included_ids = [str(file_id) for file_id in payload.included_file_ids]
    parent_run_id = str(payload.parent_run_id) if payload.parent_run_id else None
    run_mode = payload.run_mode
    if parent_run_id:
        run_mode = "fast"
    # Allow research and vector search for oneshot mode
    enable_vector_store = payload.enable_vector_store
    enable_web_search = payload.enable_web_search
    options = RunOptions(
        interactive=payload.interactive,
        project_identifier=payload.project_identifier,
        run_mode=run_mode,
        research_mode=payload.research_mode.value,
        instructions_override=payload.instructions,
        enable_vector_store=enable_vector_store,
        enable_web_search=enable_web_search,
        included_file_ids=included_ids,
        parent_run_id=parent_run_id,
        variables_delta=payload.what_to_change,
        template_id=payload.template_id,
        template_type=payload.template_type,
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
        return _db_run_to_response(run, db)

    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")


@run_router.get("/{run_id}", response_model=RunStatusResponse)
async def get_run_by_id(run_id: UUID, request: Request, db: Session = Depends(db_session)) -> RunStatusResponse:
    # Check in-memory job first (for active runs), then fall back to DB
    registry = _registry(request)
    job = registry.get_job(run_id)
    if job is not None:
        return _job_to_response(job)
    
    # Fall back to DB
    run = db.get(models.Run, run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    return _db_run_to_response(run, db)


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


@run_router.post("/{run_id}/generate-questions")
async def generate_run_questions(
    run_id: UUID,
    db: Session = Depends(db_session),
    storage: StorageBackend = Depends(get_storage),
):
    """
    Generate clarifying questions for a completed run's scope document.
    Returns questions for both experts (solutions architects) and clients.
    """
    from server.core.llm import ClaudeExtractor

    run = db.get(models.Run, run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    if run.status != "success":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Run must be successful before generating questions")

    # Find the rendered doc artifact
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
        scope_markdown = local_path.read_text(encoding="utf-8")
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to read artifact: {exc}")

    # Generate questions using Claude
    try:
        extractor = ClaudeExtractor()
        questions = extractor.generate_questions(scope_markdown=scope_markdown)
    except Exception as exc:
        logger.exception("Failed to generate questions")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to generate questions: {exc}")

    # Store questions in the run params
    params = dict(run.params or {})
    params["questions_for_expert"] = questions.get("questions_for_expert", [])
    params["questions_for_client"] = questions.get("questions_for_client", [])
    run.params = params
    db.add(run)
    db.commit()

    return questions


class GenerateMoreQuestionsRequest(BaseModel):
    question_type: str = Field(..., description="Type of questions: 'expert' or 'client'")
    existing_questions: List[str] = Field(default=[], description="List of existing questions to avoid duplicates")


class AmbiguityItem(BaseModel):
    statement: str = Field(..., description="The ambiguous statement from the document")
    section: str = Field(..., description="Which section this appears in")
    concern: str = Field(..., description="Why this is ambiguous and could cause scope creep")
    suggestion: str = Field(..., description="Suggested clarification or rewording")


class AmbiguityCheckResponse(BaseModel):
    ambiguities: List[AmbiguityItem] = Field(default=[], description="List of detected ambiguities")
    risk_level: str = Field(..., description="Overall risk level: 'low', 'medium', or 'high'")
    summary: str = Field(..., description="Brief summary of the analysis")


class SaveMarkdownRequest(BaseModel):
    markdown: str = Field(..., description="The edited markdown content")
    version: int = Field(..., description="The version number being edited")


@run_router.post("/{run_id}/generate-more-questions")
async def generate_more_questions(
    run_id: UUID,
    request: GenerateMoreQuestionsRequest,
    db: Session = Depends(db_session),
    storage: StorageBackend = Depends(get_storage),
):
    """
    Generate additional questions for a run, avoiding duplicates of existing questions.
    """
    from server.core.llm import ClaudeExtractor

    run = db.get(models.Run, run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    if run.status != "success":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Run must be successful before generating questions")

    # Find the rendered doc artifact
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
        scope_markdown = local_path.read_text(encoding="utf-8")
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to read artifact: {exc}")

    # Build context for generating more questions
    existing_list = "\n".join([f"- {q}" for q in request.existing_questions])
    question_type_label = "technical expert (solutions architect)" if request.question_type == "expert" else "client"
    
    extra_prompt = f"""
You have already generated these questions for the {question_type_label}:
{existing_list}

Now generate 3-5 NEW, high-value questions that are NOT duplicates of the above.
Focus on questions that would reveal important missing details or clarify ambiguous requirements.
If you cannot think of any valuable new questions, return an empty list.
Only return questions for the {question_type_label}, not both types.
"""

    # Generate more questions using Claude
    try:
        extractor = ClaudeExtractor()
        # Use the same generate_questions method but with extra context
        questions = extractor.generate_questions(
            scope_markdown=scope_markdown,
            extra_context=extra_prompt
        )
    except Exception as exc:
        logger.exception("Failed to generate more questions")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to generate questions: {exc}")

    # Get the relevant questions based on type
    if request.question_type == "expert":
        new_questions = questions.get("questions_for_expert", [])
    else:
        new_questions = questions.get("questions_for_client", [])

    # Filter out any duplicates that might have slipped through
    existing_lower = set(q.lower().strip() for q in request.existing_questions)
    unique_new = [q for q in new_questions if q.lower().strip() not in existing_lower]

    # Append to existing questions in run params
    params = dict(run.params or {})
    param_key = f"questions_for_{request.question_type}"
    current_questions = params.get(param_key, [])
    params[param_key] = current_questions + unique_new
    run.params = params
    db.add(run)
    db.commit()

    return {"new_questions": unique_new, "total_questions": len(params[param_key])}


@run_router.post("/{run_id}/check-ambiguity", response_model=AmbiguityCheckResponse)
async def check_run_ambiguity(
    run_id: UUID,
    db: Session = Depends(db_session),
    storage: StorageBackend = Depends(get_storage),
):
    """
    Analyze the scope document for ambiguous statements that could lead to scope creep.
    Uses LLM to identify vague language, unclear deliverables, and potential misinterpretations.
    """
    from server.core.llm import ClaudeExtractor

    run = db.get(models.Run, run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    if run.status != "success":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Run must be successful before checking ambiguity")

    # Find the rendered doc artifact
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
        scope_markdown = local_path.read_text(encoding="utf-8")
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to read artifact: {exc}")

    # Create a step record for the ambiguity check
    from uuid import uuid4
    from datetime import datetime as dt
    step_id = uuid4()
    step = models.RunStep(
        id=step_id,
        run_id=run_id,
        name="Check Ambiguity",
        status="running",
        started_at=dt.utcnow(),
    )
    db.add(step)
    db.commit()

    # Analyze for ambiguity using Claude
    try:
        extractor = ClaudeExtractor()
        result = extractor.check_ambiguity(scope_markdown=scope_markdown)
        
        # Mark step as success
        step.status = "success"
        step.finished_at = dt.utcnow()
        db.add(step)
        db.commit()
    except Exception as exc:
        # Mark step as failed
        step.status = "failed"
        step.finished_at = dt.utcnow()
        step.logs = str(exc)
        db.add(step)
        db.commit()
        
        logger.exception("Failed to check ambiguity")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to analyze document: {exc}")

    return AmbiguityCheckResponse(
        ambiguities=[AmbiguityItem(**item) for item in result.get("ambiguities", [])],
        risk_level=result.get("risk_level", "low"),
        summary=result.get("summary", "No significant ambiguities detected."),
    )


@run_router.post("/{run_id}/save-markdown")
async def save_run_markdown(
    run_id: UUID,
    request: SaveMarkdownRequest,
    db: Session = Depends(db_session),
):
    """
    Save edited markdown content for a run version.
    Creates a new sub-version entry (e.g., 1.1, 1.2, 2.1) that appears in the version dropdown.
    """
    run = db.get(models.Run, run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

    base_version = int(request.version)  # The major version being edited (1, 2, 3, etc.)
    
    # Find the highest sub-version for this major version
    # Sub-versions are like 1.1, 1.2, 2.1, 2.2 etc.
    existing_sub_versions = (
        db.query(models.RunVersion)
        .filter(
            models.RunVersion.run_id == run_id,
            models.RunVersion.version_number >= base_version,
            models.RunVersion.version_number < base_version + 1
        )
        .all()
    )
    
    # Calculate next sub-version number
    if existing_sub_versions:
        max_sub = max(v.version_number for v in existing_sub_versions)
        # If max is whole number (e.g., 2), next is 2.1
        # If max is 2.3, next is 2.4
        if max_sub == base_version:
            next_version = base_version + 0.1
        else:
            next_version = max_sub + 0.1
    else:
        # No sub-versions yet, create X.1
        next_version = base_version + 0.1
    
    # Round to avoid floating point issues
    next_version = round(next_version, 1)
    sub_version = int(round((next_version - base_version) * 10))
    
    # Create a step record for this edit
    step = _create_step(db, run_id, f"Edit Markdown v{base_version} → v{next_version}")
    
    try:
        # Create a new RunVersion entry for this sub-version
        new_version = models.RunVersion(
            run_id=run_id,
            version_number=next_version,
            markdown=request.markdown,
            feedback={"parent_version": base_version, "edit_number": sub_version},
            questions_for_expert=[],
            questions_for_client=[],
            graphic_path=None,
            regen_context=f"Manual edit of v{base_version}",
        )
        db.add(new_version)
        db.commit()
        db.refresh(new_version)
        
        _finish_step(db, step, "success", f"Saved as v{next_version}")
        return {
            "success": True,
            "version": base_version,
            "sub_version": sub_version,
            "version_number": next_version,
            "message": f"Saved as v{next_version}",
        }
    except Exception as exc:
        logger.exception(f"Failed to save markdown for run {run_id}")
        _finish_step(db, step, "failed", str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save markdown: {exc}"
        )


class AutoSaveRequest(BaseModel):
    """Request for auto-saving as a sub-version."""
    markdown: str = Field(..., description="The markdown content to auto-save")


@run_router.post("/{run_id}/auto-save")
async def auto_save_subversion(
    run_id: UUID,
    request: AutoSaveRequest,
    db: Session = Depends(db_session),
):
    """
    Auto-save as a sub-version without creating a major version.
    Used when user accepts AI edits - saves progress without committing.
    """
    run = db.get(models.Run, run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

    # Find the latest version to determine the major version
    latest_version = (
        db.query(models.RunVersion)
        .filter(models.RunVersion.run_id == run_id)
        .order_by(models.RunVersion.version_number.desc())
        .first()
    )

    if latest_version:
        current_major = int(latest_version.version_number)
        current_sub = latest_version.version_number
    else:
        current_major = 1
        current_sub = 1.0

    # Calculate next sub-version
    if current_sub == current_major:
        next_version = current_major + 0.1
    else:
        next_version = current_sub + 0.1
    
    next_version = round(next_version, 1)

    try:
        new_version = models.RunVersion(
            run_id=run_id,
            version_number=next_version,
            markdown=request.markdown,
            feedback={"auto_save": True, "parent_major": current_major},
            regen_context="Auto-saved after AI edit",
        )
        db.add(new_version)
        db.commit()
        db.refresh(new_version)

        return {
            "success": True,
            "version_number": next_version,
            "is_subversion": True,
            "message": f"Auto-saved as v{next_version}",
        }
    except Exception as exc:
        logger.exception(f"Failed to auto-save for run {run_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to auto-save: {exc}"
        )


class CommitVersionRequest(BaseModel):
    """Request for committing as a new major version."""
    markdown: str = Field(..., description="The markdown content to commit")
    base_version: int = Field(..., description="The current major version number")


@run_router.post("/{run_id}/commit-version")
async def commit_version(
    run_id: UUID,
    request: CommitVersionRequest,
    db: Session = Depends(db_session),
):
    """
    Commit all changes as a new major version.
    Creates version N+1 from the current major version N.
    """
    run = db.get(models.Run, run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

    # The next major version is base_version + 1
    next_major = request.base_version + 1

    # Check if this major version already exists
    existing = (
        db.query(models.RunVersion)
        .filter(
            models.RunVersion.run_id == run_id,
            models.RunVersion.version_number == next_major
        )
        .first()
    )
    
    if existing:
        # Update existing version
        existing.markdown = request.markdown
        existing.feedback = {"committed_from": request.base_version}
        existing.regen_context = f"Committed from v{request.base_version}"
        db.commit()
        db.refresh(existing)
        
        return {
            "success": True,
            "version_number": next_major,
            "is_subversion": False,
            "message": f"Updated v{next_major}",
        }

    try:
        new_version = models.RunVersion(
            run_id=run_id,
            version_number=float(next_major),
            markdown=request.markdown,
            feedback={"committed_from": request.base_version},
            regen_context=f"Committed from v{request.base_version}",
        )
        db.add(new_version)
        db.commit()
        db.refresh(new_version)

        return {
            "success": True,
            "version_number": next_major,
            "is_subversion": False,
            "message": f"Committed as v{next_major}",
        }
    except Exception as exc:
        logger.exception(f"Failed to commit version for run {run_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to commit version: {exc}"
        )


@run_router.delete("/{run_id}/versions/{version_number}")
async def delete_version(
    run_id: UUID,
    version_number: float,
    db: Session = Depends(db_session),
):
    """
    Delete a specific version.
    Cannot delete version 1 (original).
    """
    run = db.get(models.Run, run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

    # Prevent deletion of original version
    if version_number == 1 or abs(version_number - 1.0) < 0.001:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete the original version (v1)"
        )

    # Find the version
    version = (
        db.query(models.RunVersion)
        .filter(
            models.RunVersion.run_id == run_id,
            models.RunVersion.version_number == version_number
        )
        .first()
    )

    if not version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Version {version_number} not found"
        )

    try:
        db.delete(version)
        db.commit()

        return {
            "success": True,
            "message": f"Deleted v{version_number}",
        }
    except Exception as exc:
        logger.exception(f"Failed to delete version {version_number} for run {run_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete version: {exc}"
        )


class IndexDocumentsRequest(BaseModel):
    """Request for indexing documents for a run."""
    version: Optional[float] = Field(None, description="Version to index (default: latest)")


@run_router.post("/{run_id}/index-documents")
async def index_run_documents(
    run_id: UUID,
    request: IndexDocumentsRequest,
    db: Session = Depends(db_session),
):
    """
    Index the current document and input files for semantic search within this run.
    Creates embeddings that can be used for chat context.
    """
    from server.db.session import engine
    from server.services.vector_store import VectorStore
    from server.core.history_profiles import ProfileEmbedder
    from server.core.config import HISTORY_EMBEDDING_MODEL
    
    run = db.get(models.Run, run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

    try:
        vector_store = VectorStore(engine)
        embedder = ProfileEmbedder(HISTORY_EMBEDDING_MODEL)
        
        # Clear existing embeddings for this run
        deleted = vector_store.delete_run_embeddings(run_id)
        logger.info(f"Deleted {deleted} existing embeddings for run {run_id}")
        
        indexed_count = 0
        
        # Get the document content
        version_number = request.version
        document_content = ""
        
        if version_number:
            # Load specific version
            version = (
                db.query(models.RunVersion)
                .filter(
                    models.RunVersion.run_id == run_id,
                    models.RunVersion.version_number == version_number
                )
                .first()
            )
            if version and version.markdown:
                document_content = version.markdown
        
        if not document_content:
            # Load from artifact
            artifact = (
                db.query(models.Artifact)
                .filter(
                    models.Artifact.run_id == run_id,
                    models.Artifact.kind == "rendered_doc"
                )
                .first()
            )
            if artifact and artifact.path:
                artifact_path = Path(artifact.path)
                if artifact_path.exists():
                    document_content = artifact_path.read_text()
                    version_number = 1.0
        
        # Chunk and embed the output document
        output_chunks = 0
        if document_content:
            # Simple chunking by paragraphs (could be improved)
            chunks = [c.strip() for c in document_content.split("\n\n") if c.strip()]
            
            for i, chunk in enumerate(chunks):
                if len(chunk) < 10:  # Skip very short chunks
                    continue
                    
                # Get embedding
                embedding = list(embedder.embed(chunk))
                
                # Store embedding with doc_type metadata
                vector_store.upsert_run_embedding(
                    embedding=embedding,
                    project_id=run.project_id,
                    run_id=run_id,
                    version_number=version_number or 1.0,
                    doc_kind="document_chunk",
                    chunk_index=i,
                    chunk_text=chunk,
                    metadata={
                        "doc_type": "output",
                        "file_name": "scope_document",
                    }
                )
                indexed_count += 1
                output_chunks += 1
        
        # Index input files
        input_chunks = 0
        input_file_ids = run.included_file_ids or []
        
        if input_file_ids:
            from server.core.ingest import DocumentIngester
            ingester = DocumentIngester()
            
            for file_id in input_file_ids:
                try:
                    # Get the project file
                    project_file = db.get(models.ProjectFile, file_id)
                    if not project_file or not project_file.path:
                        logger.warning(f"ProjectFile {file_id} not found or has no path")
                        continue
                    
                    file_path = Path(project_file.path)
                    if not file_path.exists():
                        logger.warning(f"File path does not exist: {file_path}")
                        continue
                    
                    # Use DocumentIngester to extract text
                    doc_data = ingester.ingest_file(file_path)
                    if not doc_data:
                        logger.warning(f"Could not ingest file: {file_path}")
                        continue
                    
                    # Handle list return (e.g., chunked PDFs)
                    if isinstance(doc_data, list):
                        text_content = "\n\n".join(d.get("content", "") for d in doc_data if d.get("content"))
                    else:
                        text_content = doc_data.get("content", "")
                    
                    if not text_content or len(text_content) < 10:
                        continue
                    
                    # Chunk the content
                    chunks = [c.strip() for c in text_content.split("\n\n") if c.strip() and len(c.strip()) > 10]
                    
                    for i, chunk in enumerate(chunks):
                        embedding = list(embedder.embed(chunk))
                        vector_store.upsert_run_embedding(
                            embedding=embedding,
                            project_id=run.project_id,
                            run_id=run_id,
                            version_number=None,  # Input files don't have versions
                            doc_kind="input_chunk",
                            chunk_index=i,
                            chunk_text=chunk,
                            metadata={
                                "doc_type": "input",
                                "file_name": project_file.filename,
                                "file_id": str(file_id),
                            }
                        )
                        indexed_count += 1
                        input_chunks += 1
                        
                except Exception as file_exc:
                    logger.exception(f"Failed to index input file {file_id}: {file_exc}")
                    continue
        
        logger.info(f"Indexed {output_chunks} output chunks and {input_chunks} input chunks for run {run_id}")
        
        return {
            "success": True,
            "indexed_chunks": indexed_count,
            "output_chunks": output_chunks,
            "input_chunks": input_chunks,
            "deleted_old": deleted,
            "version": version_number or 1.0,
            "message": f"Indexed {indexed_count} chunks ({output_chunks} output, {input_chunks} input)",
        }
        
    except Exception as exc:
        logger.exception(f"Failed to index documents for run {run_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to index documents: {exc}"
        )


class SaveQuestionsStateRequest(BaseModel):
    expert_answers: Dict[str, str] = Field(default_factory=dict)
    client_answers: Dict[str, str] = Field(default_factory=dict)
    expert_locked: bool = False
    client_locked: bool = False
    checked_expert: List[int] = Field(default_factory=list)
    checked_client: List[int] = Field(default_factory=list)


@run_router.post("/{run_id}/save-questions-state")
async def save_questions_state(
    run_id: UUID,
    request: SaveQuestionsStateRequest,
    db: Session = Depends(db_session),
):
    """
    Save the questions answers and lock state for a run.
    This persists across page reloads.
    """
    from sqlalchemy.orm.attributes import flag_modified
    
    run = db.get(models.Run, run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    
    # Store questions state in run params
    params = dict(run.params or {})
    params["questions_state"] = {
        "expert_answers": request.expert_answers,
        "client_answers": request.client_answers,
        "expert_locked": request.expert_locked,
        "client_locked": request.client_locked,
        "checked_expert": request.checked_expert,
        "checked_client": request.checked_client,
    }
    run.params = params
    flag_modified(run, "params")
    
    db.add(run)
    db.commit()
    
    return {"success": True, "message": "Questions state saved"}


@run_router.get("/{run_id}/download-docx")
async def download_run_docx(
    run_id: UUID,
    version: Optional[int] = Query(None, description="Version number to download (1 = original, 2+ = regenerated)"),
    db: Session = Depends(db_session),
    storage: StorageBackend = Depends(get_storage),
):
    run = db.get(models.Run, run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    if run.status != "success":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Run must be successful before exporting")

    content: str = ""
    filename_stem = f"run-{run.id}"

    # If version > 1, get markdown from RunVersion table
    if version and version > 1:
        run_version = (
            db.query(models.RunVersion)
            .filter(models.RunVersion.run_id == run_id, models.RunVersion.version_number == version)
            .first()
        )
        if run_version is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Version {version} not found")
        if not run_version.markdown:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Version has no markdown content")
        content = run_version.markdown
        filename_stem = f"run-{run.id}-v{version}"
    else:
        # Get from artifact (v1 / original)
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

        filename_stem = Path(artifact.path).stem or filename_stem

    buffer = markdown_to_docx_bytes(content)
    docx_filename = f"{filename_stem}.docx"

    headers = {
        "Content-Disposition": f'attachment; filename="{docx_filename}"'
    }
    media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    return StreamingResponse(buffer, media_type=media_type, headers=headers)


@run_router.get("/{run_id}/download-md")
async def download_run_md(
    run_id: UUID,
    version: Optional[int] = Query(None, description="Version number to download (1 = original, 2+ = regenerated)"),
    db: Session = Depends(db_session),
    storage: StorageBackend = Depends(get_storage),
):
    run = db.get(models.Run, run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    if run.status != "success":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Run must be successful before exporting")

    data: bytes = b""
    filename = f"run-{run.id}.md"

    # If version > 1, get markdown from RunVersion table
    if version and version > 1:
        run_version = (
            db.query(models.RunVersion)
            .filter(models.RunVersion.run_id == run_id, models.RunVersion.version_number == version)
            .first()
        )
        if run_version is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Version {version} not found")
        if not run_version.markdown:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Version has no markdown content")
        data = run_version.markdown.encode("utf-8")
        filename = f"run-{run.id}-v{version}.md"
    else:
        # Get from artifact (v1 / original)
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

        filename = Path(artifact.path).name or filename

    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"'
    }
    media_type = "text/markdown; charset=utf-8"
    return StreamingResponse(io.BytesIO(data), media_type=media_type, headers=headers)


@run_router.get("/{run_id}/solution-graphic")
async def get_solution_graphic(
    run_id: UUID,
    db: Session = Depends(db_session),
    storage: StorageBackend = Depends(get_storage),
):
    """Get the solution graphic image if available."""
    run = db.get(models.Run, run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    if run.status != "success":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Run must be successful")

    artifact = (
        db.query(models.Artifact)
        .filter(models.Artifact.run_id == run_id, models.Artifact.kind == "solution_graphic")
        .order_by(models.Artifact.created_at.desc())
        .first()
    )

    if artifact is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No solution graphic available")

    project_id_str = str(run.project_id)

    try:
        local_path = await _ensure_artifact_local(project_id_str, artifact, storage)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to download artifact: {exc}")

    if not local_path.exists() or not local_path.is_file():
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Image file is unavailable")

    data = local_path.read_bytes()
    mime_type = artifact.meta.get("type", "image/png")
    
    return StreamingResponse(io.BytesIO(data), media_type=mime_type)


class RegenerateGraphicRequest(BaseModel):
    additional_prompt: Optional[str] = None


@run_router.post("/{run_id}/regenerate-graphic")
async def regenerate_solution_graphic(
    run_id: UUID,
    request: RegenerateGraphicRequest,
    db: Session = Depends(db_session),
    storage: StorageBackend = Depends(get_storage),
):
    """Regenerate the solution graphic for a run with optional additional prompt."""
    from server.core.image_gen import generate_scope_image, ImageGenError
    from datetime import datetime as dt
    from uuid import uuid4
    
    run = db.get(models.Run, run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    if run.status != "success":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Run must be successful")

    # Get the rendered doc artifact to extract solution text
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

    # Read markdown and extract proposed solution
    try:
        markdown_content = local_path.read_text(encoding="utf-8")
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to read document: {exc}")

    # Extract proposed solution section
    solution_text = ""
    in_solution = False
    for line in markdown_content.split("\n"):
        if "## Proposed Solution" in line or "## Solution Overview" in line:
            in_solution = True
            continue
        elif in_solution and line.startswith("## "):
            break
        elif in_solution:
            solution_text += line + "\n"
    
    if not solution_text.strip():
        # Fallback - use first 2000 chars of document
        solution_text = markdown_content[:2000]

    # Get team settings for base prompt
    base_prompt = None
    try:
        project = db.query(models.Project).filter_by(id=run.project_id).first()
        if project and project.team_id:
            team = db.query(models.Team).filter_by(id=project.team_id).first()
            if team and team.settings:
                # Use PSO or scope prompt based on template type
                if run.template_type and "pso" in run.template_type.lower():
                    base_prompt = team.settings.get("pso_image_prompt")
                else:
                    base_prompt = team.settings.get("image_prompt")
    except Exception as e:
        logger.warning(f"Failed to load team settings for graphic regen: {e}")

    # Combine prompts
    custom_prompt = base_prompt or ""
    if request.additional_prompt:
        custom_prompt = f"{custom_prompt}\n\nAdditional instructions: {request.additional_prompt}".strip()

    # Generate the image
    try:
        logger.info(f"REGEN_GRAPHIC: Starting for run {run_id}, template_type={run.template_type}, prompt_len={len(custom_prompt or '')}")
        result = generate_scope_image(
            solution_text=solution_text[:2000],
            custom_prompt=custom_prompt if custom_prompt else None,
        )
        logger.info(f"REGEN_GRAPHIC: Generated {len(result.data)} bytes, mime={result.mime_type}")
    except ImageGenError as exc:
        logger.error(f"REGEN_GRAPHIC FAILED (ImageGenError) for run {run_id}: {exc}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Image generation failed: {exc}")
    except Exception as exc:
        logger.exception(f"REGEN_GRAPHIC CRASHED for run {run_id}: {type(exc).__name__}: {exc}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Unexpected error: {exc}")

    # Save the new image
    project_runs_dir = Path(f"projects/{project_id_str}/runs/{run_id}")
    project_runs_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = dt.now().strftime("%Y%m%d_%H%M%S")
    ext = "png" if "png" in result.mime_type else "jpg"
    image_filename = f"solution_graphic_{timestamp}.{ext}"
    image_path = project_runs_dir / image_filename
    
    with open(image_path, "wb") as f:
        f.write(result.data)

    # Update or create artifact
    existing_artifact = (
        db.query(models.Artifact)
        .filter(models.Artifact.run_id == run_id, models.Artifact.kind == "solution_graphic")
        .first()
    )
    
    if existing_artifact:
        existing_artifact.path = str(image_path)
        existing_artifact.meta = {"type": result.mime_type}
        db.add(existing_artifact)
    else:
        new_artifact = models.Artifact(
            id=uuid4(),
            run_id=run_id,
            kind="solution_graphic",
            path=str(image_path),
            meta={"type": result.mime_type},
        )
        db.add(new_artifact)
    
    db.commit()

    return StreamingResponse(io.BytesIO(result.data), media_type=result.mime_type)


@run_router.post("/{run_id}/export-google-doc")
async def export_run_google_doc(
    run_id: UUID,
    force: bool = Query(False, description="Force creation of new doc even if one exists"),
    version: int = Query(None, description="Version number to export (defaults to latest)"),
    current_user: SessionUser = Depends(get_current_user),
    db: Session = Depends(db_session),
    storage: StorageBackend = Depends(get_storage),
):
    """
    Export a run's rendered markdown document to Google Docs and return the Doc link.

    This is an on-demand operation and will create (or reuse) a single Google Doc
    per version. The resulting Doc URL is stored on the version or artifact metadata.
    """
    # Import Google client libraries lazily so the backend can still run without them.
    # On Python 3.8, importlib.metadata lacks packages_distributions, which some
    # google libraries expect. Shim it using importlib-metadata backport.
    # Hard shim for py3.8: ensure importlib.metadata has packages_distributions.
    try:
        import importlib.metadata as _ilm  # type: ignore
    except Exception:  # pragma: no cover - defensive
        _ilm = None

    if _ilm:
        missing_attr = not hasattr(_ilm, "packages_distributions")
        if missing_attr:
            try:
                import importlib_metadata as _ilm_backport  # type: ignore
                import sys as _sys

                _sys.modules["importlib.metadata"] = _ilm_backport
                _ilm = _ilm_backport
            except Exception:
                pass

        if not hasattr(_ilm, "packages_distributions"):
            def _pd_shim():  # type: ignore
                return {}

            try:
                _ilm.packages_distributions = _pd_shim  # type: ignore[attr-defined]
            except Exception:
                # Last resort: inject into module dict
                import sys as _sys  # type: ignore
                _sys.modules.get("importlib.metadata", _ilm).__dict__["packages_distributions"] = _pd_shim

    try:
        from google.oauth2.credentials import Credentials  # type: ignore
        from googleapiclient.discovery import build  # type: ignore
        from server.core.markdown_to_googledocs import (
            create_google_doc_from_markdown,
            get_google_doc_url,
        )
    except Exception as exc:  # pragma: no cover - defensive import guard
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Google Docs integration unavailable: {exc}",
        )

    from datetime import datetime as dt
    
    run = db.get(models.Run, run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    if run.status != "success":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Run must be successful before exporting")

    # Create a step record for this export
    step = _create_step(db, run_id, f"Export to Google Doc{' v' + str(version) if version else ''}")
    # Try to get content from a specific version if requested
    run_version = None
    content = None
    version_label = ""
    
    if version is not None:
        run_version = (
            db.query(models.RunVersion)
            .filter(models.RunVersion.run_id == run_id, models.RunVersion.version_number == version)
            .first()
        )
        if run_version and run_version.markdown:
            content = run_version.markdown
            version_label = f" (v{version})"
            # Check if this version already has a Google Doc
            # Store doc info in version feedback for now
            version_meta = run_version.feedback or {}
            existing_url = version_meta.get("google_doc_url")
            existing_id = version_meta.get("google_doc_id")
            if existing_url and existing_id and not force:
                return {"doc_id": existing_id, "doc_url": existing_url, "status": "existing", "version": version}

    # Fall back to artifact if no version content
    artifact = None
    if content is None:
        artifact = (
            db.query(models.Artifact)
            .filter(models.Artifact.run_id == run_id, models.Artifact.kind == "rendered_doc")
            .order_by(models.Artifact.created_at.desc())
            .first()
        )

        if artifact is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Rendered document not found")

        # If we've already created a Google Doc for this artifact, return it (unless force=True)
        existing_url = (artifact.meta or {}).get("google_doc_url")
        existing_id = (artifact.meta or {}).get("google_doc_id")
        if existing_url and existing_id and not force:
            return {"doc_id": existing_id, "doc_url": existing_url, "status": "existing"}

        project_id_str = str(run.project_id)

        try:
            local_path = await _ensure_artifact_local(project_id_str, artifact, storage)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to download artifact: {exc}",
            )

        if not local_path.exists() or not local_path.is_file():
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Rendered document is unavailable",
            )

        try:
            content = local_path.read_text(encoding="utf-8")
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to read artifact: {exc}",
            )

    # Get project name for the title
    project = db.get(models.Project, run.project_id)
    project_name = project.name if project else "Scope"
    
    # Create title with date and version
    today = dt.now().strftime("%Y-%m-%d")
    title = f"{project_name} - {today}{version_label}"

    # Build per-user Google API clients using OAuth tokens with refresh capability
    token_data = get_user_google_tokens(current_user.id, db)
    
    if not token_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google account not connected or token expired. Please reconnect your Google account in Settings.",
        )

    creds = credentials_from_tokens(token_data)
    if not creds:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Failed to create Google credentials. Please reconnect your Google account in Settings.",
        )
    
    # Refresh credentials if expired
    if creds.expired and creds.refresh_token:
        try:
            from google.auth.transport.requests import Request
            creds.refresh(Request())
            logger.info(f"Refreshed Google OAuth token for user {current_user.id}")
        except Exception as refresh_exc:
            logger.warning(f"Failed to refresh Google token: {refresh_exc}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Google token expired and refresh failed. Please reconnect your Google account in Settings.",
            )
    
    drive_service = build("drive", "v3", credentials=creds)
    docs_service = build("docs", "v1", credentials=creds)

    try:
        doc_id = await run_in_threadpool(
            create_google_doc_from_markdown,
            content,
            title,
            drive_service,
            docs_service,
        )
    except Exception as exc:
        logger.exception("Failed to create Google Doc")
        message = str(exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to create Google Doc: {message}",
        )

    doc_url = get_google_doc_url(doc_id)

    # Persist the association for future reuse
    if run_version:
        # Save to version's feedback JSONB
        from sqlalchemy.orm.attributes import flag_modified
        version_meta = dict(run_version.feedback or {})
        version_meta.update({
            "google_doc_id": doc_id,
            "google_doc_url": doc_url,
        })
        run_version.feedback = version_meta
        flag_modified(run_version, "feedback")
        db.add(run_version)
    elif artifact:
        # Save to artifact metadata
        meta = dict(artifact.meta or {})
        meta.update({
            "google_doc_id": doc_id,
            "google_doc_url": doc_url,
        })
        artifact.meta = meta
        db.add(artifact)
    
    db.commit()

    result = {"doc_id": doc_id, "doc_url": doc_url, "status": "created"}
    if version:
        result["version"] = version
    return result


# =============================================================================
# Run Versioning Endpoints
# =============================================================================

class RunVersionResponse(BaseModel):
    id: UUID
    run_id: UUID
    version_number: float
    markdown: Optional[str] = None
    feedback: Optional[dict] = None
    questions_for_expert: Optional[List[str]] = None
    questions_for_client: Optional[List[str]] = None
    graphic_path: Optional[str] = None
    created_at: datetime
    regen_context: Optional[str] = None
    google_doc_url: Optional[str] = None
    google_doc_id: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class RegenerateRequest(BaseModel):
    answers: str = Field(..., description="Answers to questions or context for regeneration")
    regen_graphic: bool = Field(False, description="Whether to regenerate the solution graphic")
    extra_research: bool = Field(False, description="Whether to perform additional research")
    research_provider: str = Field("claude", pattern="^(claude|perplexity)$", description="Research provider if extra_research is enabled")


class RegenerateResponse(BaseModel):
    version_id: UUID
    version_number: float
    message: str


@run_router.get("/{run_id}/versions", response_model=List[RunVersionResponse])
async def list_run_versions(
    run_id: UUID,
    db: Session = Depends(db_session),
    current_user: SessionUser = Depends(get_current_user),
):
    """List all versions for a run."""
    run = db.get(models.Run, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    
    versions = (
        db.query(models.RunVersion)
        .filter(models.RunVersion.run_id == run_id)
        .order_by(models.RunVersion.version_number.desc())
        .all()
    )
    
    # Map versions to response, extracting google_doc_url from feedback
    result = []
    for v in versions:
        feedback = v.feedback or {}
        result.append(RunVersionResponse(
            id=v.id,
            run_id=v.run_id,
            version_number=v.version_number,
            markdown=v.markdown,
            feedback=feedback,
            questions_for_expert=v.questions_for_expert,
            questions_for_client=v.questions_for_client,
            graphic_path=v.graphic_path,
            created_at=v.created_at,
            regen_context=v.regen_context,
            google_doc_url=feedback.get("google_doc_url"),
            google_doc_id=feedback.get("google_doc_id"),
        ))
    return result


@run_router.get("/{run_id}/versions/{version_number}", response_model=RunVersionResponse)
async def get_run_version(
    run_id: UUID,
    version_number: float,
    db: Session = Depends(db_session),
    current_user: SessionUser = Depends(get_current_user),
):
    """Get a specific version of a run."""
    run = db.get(models.Run, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    
    version = (
        db.query(models.RunVersion)
        .filter(
            models.RunVersion.run_id == run_id,
            models.RunVersion.version_number == version_number
        )
        .first()
    )
    
    if version is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Version not found")
    
    return version


class RegenJobResponse(BaseModel):
    """Response when starting a regen job."""
    job_id: UUID
    message: str


class RegenJobStatusResponse(BaseModel):
    """Response for regen job status check."""
    id: str
    run_id: str
    status: str
    created_at: Optional[str] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    version_id: Optional[str] = None
    version_number: Optional[float] = None
    error: Optional[str] = None


@run_router.post("/{run_id}/regenerate", response_model=RegenJobResponse)
async def regenerate_run(
    run_id: UUID,
    request: Request,
    payload: RegenerateRequest,
    db: Session = Depends(db_session),
    current_user: SessionUser = Depends(get_current_user),
):
    """
    Start a regeneration job for a run.
    
    This creates a background job to regenerate the scope document with the
    provided answers. Use GET /runs/{run_id}/regen-status/{job_id} to check status.
    """
    run = db.get(models.Run, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    
    if run.status != "success":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only regenerate successful runs"
        )
    
    # Get job registry and start the regen job
    registry = _registry(request)
    job = registry.create_regen_job(
        run_id=run_id,
        answers=payload.answers,
        extra_research=payload.extra_research,
        research_provider=payload.research_provider,
        regen_graphic=payload.regen_graphic,
    )
    
    logger.info(f"Started regen job {job.id} for run {run_id}")
    
    return RegenJobResponse(
        job_id=job.id,
        message="Regeneration started. Poll /regen-status/{job_id} for progress."
    )


@run_router.get("/{run_id}/regen-status/{job_id}", response_model=RegenJobStatusResponse)
async def get_regen_job_status(
    run_id: UUID,
    job_id: UUID,
    request: Request,
    db: Session = Depends(db_session),
    current_user: SessionUser = Depends(get_current_user),
):
    """Get the status of a regeneration job."""
    run = db.get(models.Run, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    
    registry = _registry(request)
    job = registry.get_regen_job(job_id)
    
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Regen job not found")
    
    if job.run_id != run_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Job does not belong to this run")
    
    return RegenJobStatusResponse(**job.to_dict())


# =============================================================================
# AI Document Chat Endpoints
# =============================================================================

class ChatRequest(BaseModel):
    """Request body for chat endpoint."""
    message: str = Field(..., description="The user's message")
    conversation_history: List[Dict[str, str]] = Field(
        default_factory=list,
        description="Previous messages in the conversation"
    )
    document_content: Optional[str] = Field(
        None,
        description="Current document content. If not provided, fetches from latest version."
    )
    version: Optional[float] = Field(
        None,
        description="Version number to use as context (can be float like 1.1)"
    )
    enable_web_search: bool = Field(False, description="Enable Claude web search")
    use_perplexity: bool = Field(False, description="Use Perplexity for deep research")


class ApplyEditRequest(BaseModel):
    """Request to apply an AI-suggested edit."""
    old_str: str = Field(..., description="Text to replace")
    new_str: str = Field(..., description="Replacement text")
    document_content: str = Field(..., description="Current document content")
    save_version: bool = Field(True, description="Save as new version after applying")


class ApplyEditResponse(BaseModel):
    """Response after applying an edit."""
    success: bool
    new_content: str
    version_number: Optional[float] = None
    message: str


@run_router.post("/{run_id}/chat")
async def chat_with_run(
    run_id: UUID,
    payload: ChatRequest,
    db: Session = Depends(db_session),
    storage: StorageBackend = Depends(get_storage),
    current_user: SessionUser = Depends(get_current_user),
):
    """
    Stream a chat response for document editing.
    
    Returns Server-Sent Events (SSE) with:
    - event: text - Streaming text content
    - event: tool - Tool call from AI (e.g., str_replace_edit)
    - event: error - Error message
    - event: done - Stream complete
    """
    from server.services.chat_service import get_chat_service, ChatMessage
    
    run = db.get(models.Run, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    
    # Get document content
    document_content = payload.document_content
    if not document_content:
        # Try to get from version or artifact
        if payload.version and payload.version > 1:
            run_version = (
                db.query(models.RunVersion)
                .filter(
                    models.RunVersion.run_id == run_id,
                    models.RunVersion.version_number == payload.version
                )
                .first()
            )
            if run_version and run_version.markdown:
                document_content = run_version.markdown
        
        if not document_content:
            # Fall back to original artifact
            artifact = (
                db.query(models.Artifact)
                .filter(models.Artifact.run_id == run_id, models.Artifact.kind == "rendered_doc")
                .order_by(models.Artifact.created_at.desc())
                .first()
            )
            if artifact:
                project_id_str = str(run.project_id)
                try:
                    local_path = await _ensure_artifact_local(project_id_str, artifact, storage)
                    document_content = local_path.read_text(encoding="utf-8")
                except Exception as exc:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"Failed to load document: {exc}"
                    )
    
    if not document_content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No document content available"
        )
    
    # Build run context
    project = db.get(models.Project, run.project_id)
    run_context = {
        "project_name": project.name if project else None,
        "template_type": run.template_type,
        "run_id": str(run_id),
    }
    
    # Convert conversation history
    history = [
        ChatMessage(role=msg.get("role", "user"), content=msg.get("content", ""))
        for msg in payload.conversation_history
    ]
    
    chat_service = get_chat_service()
    
    async def generate_sse():
        """Generate SSE events from chat stream."""
        try:
            async for event in chat_service.stream_chat(
                message=payload.message,
                document_content=document_content,
                conversation_history=history,
                run_context=run_context,
                enable_web_search=payload.enable_web_search,
                use_perplexity=payload.use_perplexity,
            ):
                yield event.to_sse()
                # Small delay to prevent overwhelming the client
                await asyncio.sleep(0.01)
        except Exception as exc:
            logger.exception(f"Chat stream error: {exc}")
            error_event = f"event: error\ndata: {json.dumps({'message': str(exc)})}\n\n"
            yield error_event
    
    return StreamingResponse(
        generate_sse(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@run_router.post("/{run_id}/apply-edit", response_model=ApplyEditResponse)
async def apply_edit_to_run(
    run_id: UUID,
    payload: ApplyEditRequest,
    db: Session = Depends(db_session),
    current_user: SessionUser = Depends(get_current_user),
):
    """
    Apply an AI-suggested edit to the document.
    
    Optionally saves as a new version.
    """
    from server.services.chat_service import get_chat_service
    
    run = db.get(models.Run, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    
    chat_service = get_chat_service()
    new_content, success = chat_service.apply_edit(
        document=payload.document_content,
        old_str=payload.old_str,
        new_str=payload.new_str,
    )
    
    if not success:
        return ApplyEditResponse(
            success=False,
            new_content=payload.document_content,
            message="Edit failed: text not found in document"
        )
    
    version_number = None
    if payload.save_version:
        # Find the latest version number
        latest_version = (
            db.query(models.RunVersion)
            .filter(models.RunVersion.run_id == run_id)
            .order_by(models.RunVersion.version_number.desc())
            .first()
        )
        
        if latest_version:
            base_version = int(latest_version.version_number)
            version_number = round(latest_version.version_number + 0.1, 1)
        else:
            base_version = 1
            version_number = 1.1
        
        # Create new version
        new_version = models.RunVersion(
            run_id=run_id,
            version_number=version_number,
            markdown=new_content,
            feedback={"edit_type": "ai_suggestion"},
            regen_context=f"AI edit: replaced '{payload.old_str[:50]}...' with '{payload.new_str[:50]}...'"
        )
        db.add(new_version)
        db.commit()
    
    return ApplyEditResponse(
        success=True,
        new_content=new_content,
        version_number=version_number,
        message=f"Edit applied successfully{' and saved as v' + str(version_number) if version_number else ''}"
    )

