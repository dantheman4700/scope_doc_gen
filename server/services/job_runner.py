"""Background job runner for scope generation tasks."""

from __future__ import annotations

import hashlib
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
import shutil
from pathlib import Path
from threading import Lock
from typing import Dict, Optional, List, Tuple
from uuid import UUID, uuid4

from server.core.main import ScopeDocGenerator
from server.core.research import ResearchMode
from server.core.config import (
    DATA_ROOT,
    HISTORY_ENABLED,
    HISTORY_EMBEDDING_MODEL,
    HISTORY_TOPN,
    STORAGE_PROVIDER,
)
from server.core.history_profiles import ProfileEmbedder
from server.core.history_retrieval import HistoryRetriever

from ..storage import ensure_project_structure
from ..db.session import get_session
from ..db import models
from ..dependencies import get_storage
from .vector_store import VectorStore


LOGGER = logging.getLogger(__name__)


class JobState(str):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


@dataclass
class RunOptions:
    interactive: bool = False
    project_identifier: Optional[str] = None
    run_mode: str = "full"
    research_mode: str = ResearchMode.QUICK.value
    instructions_override: Optional[str] = None
    enable_vector_store: bool = True
    enable_web_search: bool = True
    included_file_ids: List[str] = field(default_factory=list)
    parent_run_id: Optional[str] = None
    variables_delta: Optional[str] = None
    template_id: Optional[str] = None  # Google Drive file ID for one-shot mode templates
    template_type: Optional[str] = None  # "Scope", "PSO", etc.
    # Image generation options
    enable_image_generation: bool = False
    image_prompt: Optional[str] = None
    image_resolution: str = "4K"
    image_aspect_ratio: str = "auto"

    def to_dict(self) -> dict:
        return {
            "interactive": self.interactive,
            "project_identifier": self.project_identifier,
            "run_mode": self.run_mode,
            "research_mode": self.research_mode,
            "instructions_override": self.instructions_override,
            "enable_vector_store": self.enable_vector_store,
            "enable_web_search": self.enable_web_search,
            "included_file_ids": self.included_file_ids,
            "parent_run_id": self.parent_run_id,
            "variables_delta": self.variables_delta,
            "template_id": self.template_id,
            "template_type": self.template_type,
            "enable_image_generation": self.enable_image_generation,
            "image_prompt": self.image_prompt,
            "image_resolution": self.image_resolution,
            "image_aspect_ratio": self.image_aspect_ratio,
        }


@dataclass
class JobStatus:
    id: UUID
    project_id: str
    run_mode: str
    research_mode: str
    template_type: Optional[str] = None
    status: str = JobState.PENDING
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    result_path: Optional[str] = None
    error: Optional[str] = None
    params: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "status": self.status,
            "run_mode": self.run_mode,
            "research_mode": self.research_mode,
            "template_type": self.template_type,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "result_path": self.result_path,
            "error": self.error,
            "params": self.params,
        }


@dataclass
class RegenJobStatus:
    """Status for a regeneration job."""
    id: UUID
    run_id: UUID
    status: str = JobState.PENDING
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    version_id: Optional[UUID] = None
    version_number: Optional[int] = None
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "run_id": str(self.run_id),
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "version_id": str(self.version_id) if self.version_id else None,
            "version_number": self.version_number,
            "error": self.error,
        }


class JobRegistry:
    """In-memory job tracker backed by a thread pool executor."""

    def __init__(self, max_workers: int = 2, *, vector_store: Optional[VectorStore] = None) -> None:
        self._jobs: Dict[UUID, JobStatus] = {}
        self._regen_jobs: Dict[UUID, RegenJobStatus] = {}
        self._lock = Lock()
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._vector_store = vector_store
        self._embedder: Optional[ProfileEmbedder] = None
        self._storage = get_storage()
        self._use_remote_storage = STORAGE_PROVIDER == "supabase"

    def _load_team_settings(self, project_id: str) -> dict:
        """Load team settings for the project's team."""
        try:
            with get_session() as session:
                project = session.query(models.Project).filter_by(id=project_id).first()
                if project and project.team_id:
                    team = session.query(models.Team).filter_by(id=project.team_id).first()
                    if team and team.settings:
                        LOGGER.info(f"Loaded team settings for project {project_id}: {team.settings}")
                        return team.settings
        except Exception as e:
            LOGGER.warning(f"Failed to load team settings: {e}")
        return {}

    def _apply_team_settings(self, options: RunOptions, settings: dict) -> RunOptions:
        """Apply team-level defaults to run options."""
        # Apply image generation settings
        if settings.get("enable_solution_image") and not options.enable_image_generation:
            options.enable_image_generation = settings.get("enable_solution_image", False)
        if settings.get("image_prompt") and not options.image_prompt:
            options.image_prompt = settings.get("image_prompt")
        if settings.get("image_resolution"):
            options.image_resolution = settings.get("image_resolution", "4K")
        if settings.get("image_aspect_ratio"):
            options.image_aspect_ratio = settings.get("image_aspect_ratio", "auto")
        
        LOGGER.info(f"Applied team settings: enable_image={options.enable_image_generation}, resolution={options.image_resolution}")
        return options

    def create_job(self, project_id: str, options: RunOptions) -> JobStatus:
        # Load and apply team settings
        team_settings = self._load_team_settings(project_id)
        if team_settings:
            options = self._apply_team_settings(options, team_settings)

        job_id = uuid4()
        # Determine template_type based on run_mode (default to "Scope" for oneshot)
        template_type = options.template_type
        if not template_type:
            if options.run_mode == "oneshot":
                template_type = "Scope"
            elif options.run_mode == "full":
                template_type = "Full"
            else:
                template_type = options.run_mode.capitalize()
        
        job = JobStatus(
            id=job_id,
            project_id=project_id,
            run_mode=options.run_mode,
            research_mode=options.research_mode,
            template_type=template_type,
            params=options.to_dict(),
        )

        with self._lock:
            self._jobs[job_id] = job

        self._ensure_run_record(job, options, template_type)
        self._executor.submit(self._execute_job, job_id, options)
        return job

    def list_jobs(self, project_id: Optional[str] = None) -> list[JobStatus]:
        with self._lock:
            jobs = list(self._jobs.values())
        if project_id is not None:
            jobs = [job for job in jobs if job.project_id == project_id]
        return jobs

    def get_job(self, job_id: UUID) -> Optional[JobStatus]:
        with self._lock:
            return self._jobs.get(job_id)

    # ---------- Regen Job Methods ----------

    def create_regen_job(
        self,
        run_id: UUID,
        answers: str,
        extra_research: bool = False,
        research_provider: str = "claude",
        regen_graphic: bool = False,
    ) -> RegenJobStatus:
        """Create and start a regeneration job."""
        job_id = uuid4()
        job = RegenJobStatus(id=job_id, run_id=run_id)
        
        with self._lock:
            self._regen_jobs[job_id] = job
        
        # Submit the regen task
        self._executor.submit(
            self._execute_regen_job,
            job_id,
            run_id,
            answers,
            extra_research,
            research_provider,
            regen_graphic,
        )
        
        return job

    def get_regen_job(self, job_id: UUID) -> Optional[RegenJobStatus]:
        """Get regen job status."""
        with self._lock:
            return self._regen_jobs.get(job_id)

    def _execute_regen_job(
        self,
        job_id: UUID,
        run_id: UUID,
        answers: str,
        extra_research: bool,
        research_provider: str,
        regen_graphic: bool,
    ) -> None:
        """Execute regeneration in background thread."""
        with self._lock:
            job = self._regen_jobs.get(job_id)
            if job:
                job.status = JobState.RUNNING
                job.started_at = datetime.utcnow()
        
        # Determine version number first for the step name
        next_version_number = 2
        step_id = None
        
        try:
            with get_session() as session:
                run = session.get(models.Run, run_id)
                if not run:
                    raise ValueError(f"Run {run_id} not found")
                
                # Get current version number
                latest_version = (
                    session.query(models.RunVersion)
                    .filter(models.RunVersion.run_id == run_id)
                    .order_by(models.RunVersion.version_number.desc())
                    .first()
                )
                next_version_number = (latest_version.version_number + 1) if latest_version else 2
                
                # Start a run step for tracking in the database
                step_id = self._start_run_step(run_id, f"Regenerate Version {next_version_number}")
                
                # Get original markdown from latest version or artifact
                original_markdown = None
                if latest_version and latest_version.markdown:
                    original_markdown = latest_version.markdown
                else:
                    artifact = (
                        session.query(models.Artifact)
                        .filter(models.Artifact.run_id == run_id, models.Artifact.kind == "rendered_doc")
                        .first()
                    )
                    if artifact:
                        # Read from storage
                        local_path = Path(DATA_ROOT) / "projects" / str(run.project_id) / "output" / Path(artifact.path).name
                        if local_path.exists():
                            original_markdown = local_path.read_text(encoding="utf-8")
                
                if not original_markdown:
                    raise ValueError("No original markdown found")
                
                project_id_str = str(run.project_id)
                
                # Import LLM functions
                from server.core.llm import regenerate_with_answers, generate_questions
                
                LOGGER.info(f"Starting regen job {job_id} for run {run_id}")
                
                # Regenerate markdown
                new_markdown = regenerate_with_answers(
                    original_markdown,
                    answers,
                    extra_research,
                    research_provider,
                )
                
                # Generate questions
                try:
                    questions = generate_questions(new_markdown)
                except Exception as exc:
                    LOGGER.warning(f"Failed to generate questions for version: {exc}")
                    questions = {"questions_for_expert": [], "questions_for_client": []}
                
                # Handle graphic regeneration
                graphic_path = None
                if regen_graphic:
                    try:
                        from server.core.image_gen import generate_scope_image, GENAI_AVAILABLE
                        from server.core.config import GEMINI_IMAGE_RESOLUTION, GEMINI_IMAGE_ASPECT_RATIO
                        
                        if GENAI_AVAILABLE:
                            proposed_solution = ""
                            lines = new_markdown.split("\n")
                            in_solution = False
                            for line in lines:
                                if "## Proposed Solution" in line or "## Solution" in line:
                                    in_solution = True
                                    continue
                                if in_solution and line.startswith("## "):
                                    break
                                if in_solution:
                                    proposed_solution += line + "\n"
                            
                            if proposed_solution:
                                image_data = generate_scope_image(
                                    proposed_solution[:2000],
                                    GEMINI_IMAGE_RESOLUTION,
                                    GEMINI_IMAGE_ASPECT_RATIO,
                                )
                                
                                if image_data:
                                    version_graphic_filename = f"version_{next_version_number}_graphic.png"
                                    version_graphic_path = Path(DATA_ROOT) / "projects" / project_id_str / "output" / version_graphic_filename
                                    version_graphic_path.parent.mkdir(parents=True, exist_ok=True)
                                    version_graphic_path.write_bytes(image_data)
                                    graphic_path = str(version_graphic_path)
                    except Exception as exc:
                        LOGGER.warning(f"Failed to regenerate graphic: {exc}")
                
                # Create version record
                new_version = models.RunVersion(
                    run_id=run_id,
                    version_number=next_version_number,
                    markdown=new_markdown,
                    feedback=None,
                    questions_for_expert=questions.get("questions_for_expert", []),
                    questions_for_client=questions.get("questions_for_client", []),
                    graphic_path=graphic_path,
                    regen_context=answers,
                )
                
                session.add(new_version)
                session.commit()
                session.refresh(new_version)
                
                LOGGER.info(f"Created version {next_version_number} for run {run_id}")
                
                # Mark the step as successful in the database
                if step_id:
                    self._finish_run_step(step_id, "success", f"Created version {next_version_number}")
                
                # Update job status
                with self._lock:
                    job = self._regen_jobs.get(job_id)
                    if job:
                        job.status = JobState.SUCCESS
                        job.finished_at = datetime.utcnow()
                        job.version_id = new_version.id
                        job.version_number = next_version_number
                
        except Exception as exc:
            LOGGER.exception(f"Regen job {job_id} failed: {exc}")
            
            # Mark the step as failed in the database
            if step_id:
                self._finish_run_step(step_id, "failed", str(exc))
            
            with self._lock:
                job = self._regen_jobs.get(job_id)
                if job:
                    job.status = JobState.FAILED
                    job.finished_at = datetime.utcnow()
                    job.error = str(exc)

    # ---------- End Regen Job Methods ----------

    def _ensure_run_record(self, job: JobStatus, options: RunOptions, template_type: Optional[str] = None) -> None:
        with get_session() as session:
            run_record = session.get(models.Run, job.id)
            if run_record is None:
                run_record = models.Run(
                    id=job.id,
                    project_id=job.project_id,
                )
                session.add(run_record)

            run_record.mode = options.run_mode
            run_record.research_mode = options.research_mode
            run_record.template_type = template_type
            run_record.status = JobState.PENDING
            run_record.params = options.to_dict()
            run_record.included_file_ids = options.included_file_ids
            run_record.instructions = options.instructions_override

            if options.parent_run_id:
                try:
                    run_record.parent_run_id = UUID(options.parent_run_id)
                except ValueError:
                    run_record.parent_run_id = None
            else:
                run_record.parent_run_id = None

    # ------------------------------------------------------------------
    # Worker
    # ------------------------------------------------------------------
    def _execute_job(self, job_id: UUID, options: RunOptions) -> None:
        job = self.get_job(job_id)
        if job is None:
            return

        paths = ensure_project_structure(DATA_ROOT, job.project_id)
        run_dir = paths.runs_dir / str(job.id)
        run_dir.mkdir(parents=True, exist_ok=True)

        sync_step_id = self._start_run_step(job.id, "sync inputs")
        try:
            sync_errors, sync_warnings = self._prepare_workspace(
                job.project_id,
                paths,
                included_ids=options.included_file_ids,
            )
        except Exception as exc:  # pragma: no cover - defensive
            LOGGER.exception(f"Job {job_id} failed during sync: {exc}")
            self._finish_run_step(sync_step_id, "failed", str(exc))
            self._mark_failed(job, str(exc))
            self._update_run(job.id, status=JobState.FAILED, finished_at=datetime.utcnow(), error=str(exc))
            return

        if sync_errors:
            detail = "\n".join(sync_errors)
            self._finish_run_step(sync_step_id, "failed", detail)
            self._mark_failed(job, "Unable to synchronize required inputs from storage")
            self._update_run(
                job.id,
                status=JobState.FAILED,
                finished_at=datetime.utcnow(),
                error=detail,
            )
            return

        detail = "\n".join(sync_warnings) if sync_warnings else None
        self._finish_run_step(sync_step_id, "success", detail)
        if sync_warnings:
            job.params.setdefault("sync_warnings", sync_warnings)
            self._update_run(job.id, params=job.params)
        step_ids: Dict[str, UUID] = {}

        def step_callback(step: str, event: str, detail: Optional[str] = None) -> None:
            if event == "started":
                step_id = self._start_run_step(job.id, step)
                step_ids[step] = step_id
            elif event == "completed":
                step_id = step_ids.get(step)
                if step_id is None:
                    step_id = self._start_run_step(job.id, step)
                    step_ids[step] = step_id
                self._finish_run_step(step_id, "success", detail)
            elif event == "failed":
                step_id = step_ids.get(step)
                if step_id is None:
                    step_id = self._start_run_step(job.id, step)
                    step_ids[step] = step_id
                self._finish_run_step(step_id, "failed", detail)

        # Instructions are now passed directly as a parameter to generate()
        # No need to write instructions.txt file
        
        self._mark_running(job)
        self._update_run(job.id, status=JobState.RUNNING, started_at=datetime.utcnow())
        
        LOGGER.info(f"Starting job {job_id} in {options.run_mode} mode")
        LOGGER.info(f"Job options: research_mode={options.research_mode}, enable_vector_store={options.enable_vector_store}, enable_web_search={options.enable_web_search}")

        try:
            # Create history retriever if vector search is enabled and we have a vector store
            history_retriever = None
            if options.enable_vector_store:
                if not HISTORY_ENABLED:
                    LOGGER.warning("Vector search requested but HISTORY_ENABLED=false in .env - skipping vector search")
                elif not self._vector_store:
                    LOGGER.warning("Vector search requested but vector store not initialized - skipping")
                else:
                    try:
                        history_retriever = HistoryRetriever(
                            vector_store=self._vector_store,
                            model_name=HISTORY_EMBEDDING_MODEL,
                            top_n=HISTORY_TOPN,
                        )
                        LOGGER.info("History retriever initialized for vector search")
                    except Exception as hr_exc:
                        LOGGER.warning(f"Failed to initialize history retriever: {hr_exc}")

            generator = ScopeDocGenerator(
                input_dir=paths.input_dir,
                output_dir=run_dir / "outputs",
                project_dir=run_dir,
                history_retriever=history_retriever,
            )

            feedback: Optional[dict] = None

            if options.parent_run_id:
                result_path = self._run_quick_regen(job, options, generator, paths, step_callback)
            elif options.run_mode == "oneshot":
                result_path = generator.generate_oneshot(
                    project_identifier=options.project_identifier,
                    instructions=options.instructions_override,
                    step_callback=step_callback,
                    template_id=options.template_id,
                    research_mode=options.research_mode,
                    enable_vector_store=options.enable_vector_store,
                    enable_web_search=options.enable_web_search,
                    enable_image_generation=options.enable_image_generation,
                    image_prompt=options.image_prompt,
                    image_resolution=options.image_resolution,
                    image_aspect_ratio=options.image_aspect_ratio,
                )
                feedback = generator.last_feedback
            else:
                result_path = generator.generate(
                    interactive=options.interactive,
                    project_identifier=options.project_identifier,
                    smart_ingest=True,
                    context_notes_path=None,
                    date_override=None,
                    research_mode=options.research_mode,
                    run_mode=options.run_mode,
                    step_callback=step_callback,
                    allow_web_search=options.enable_web_search,
                    instructions=options.instructions_override,
                )
                feedback = generator.last_feedback
            if not result_path:
                raise ValueError("Generation returned no result path")
            
            result_rel = self._relative_to_project(paths.root, result_path)
            if self._use_remote_storage and result_rel:
                self._upload_to_storage(job.project_id, paths.root / Path(result_rel))
            
            # Update params first, then status - ensures consistency
            if feedback:
                job.params["feedback"] = feedback
            # Mark in-memory status first so live queries see completion immediately
            self._mark_success(job, result_rel)
            self._update_run(job.id, params=job.params)
            self._update_run(job.id, status=JobState.SUCCESS, finished_at=datetime.utcnow(), result_path=result_rel)
            artifact_ids = self._record_artifacts(job.id, job.project_id, paths, result_rel)
            variables_artifact_id = artifact_ids.get("variables")
            if variables_artifact_id:
                self._update_run(job.id, extracted_variables_artifact_id=variables_artifact_id)
                job.params.setdefault("extracted_variables_artifact_id", str(variables_artifact_id))
            
            # Auto-generate questions after successful completion
            self._auto_generate_questions(job, paths, result_rel)
            
            # Embedding now triggered manually via API endpoint for consistency
        except Exception as exc:  # pragma: no cover - execution safeguard
            LOGGER.exception(f"Job {job_id} failed: {exc}")
            self._mark_failed(job, str(exc))
            self._update_run(job.id, status=JobState.FAILED, finished_at=datetime.utcnow(), error=str(exc))

    def _mark_running(self, job: JobStatus) -> None:
        with self._lock:
            job.status = JobState.RUNNING
            job.started_at = datetime.utcnow()

    def _mark_success(self, job: JobStatus, result_path: Optional[str]) -> None:
        with self._lock:
            job.status = JobState.SUCCESS
            job.finished_at = datetime.utcnow()
            job.result_path = result_path

    def _mark_failed(self, job: JobStatus, error: str) -> None:
        with self._lock:
            job.status = JobState.FAILED
            job.finished_at = datetime.utcnow()
            job.error = error

    def _auto_generate_questions(self, job: JobStatus, paths, result_rel: Optional[str]) -> None:
        """Auto-generate clarifying questions after successful scope generation."""
        if not result_rel:
            return
        
        try:
            from server.core.llm import ClaudeExtractor
            
            result_path = paths.root / Path(result_rel)
            if not result_path.exists():
                LOGGER.warning(f"Result file not found for question generation: {result_path}")
                return
            
            scope_markdown = result_path.read_text(encoding="utf-8")
            LOGGER.info(f"Auto-generating questions for run {job.id}")
            
            extractor = ClaudeExtractor()
            questions = extractor.generate_questions(scope_markdown=scope_markdown)
            
            if questions.get("questions_for_expert") or questions.get("questions_for_client"):
                # Update job params with questions
                job.params["questions_for_expert"] = questions.get("questions_for_expert", [])
                job.params["questions_for_client"] = questions.get("questions_for_client", [])
                self._update_run(job.id, params=job.params)
                LOGGER.info(f"Auto-generated {len(questions.get('questions_for_expert', []))} expert questions, "
                           f"{len(questions.get('questions_for_client', []))} client questions")
            else:
                LOGGER.warning("Question generation returned empty results")
        except Exception as exc:
            LOGGER.exception(f"Auto question generation failed for job {job.id}: {exc}")

    def _update_run(self, run_id: UUID, **updates) -> None:
        with get_session() as session:
            run = session.get(models.Run, run_id)
            if not run:
                return
            for key, value in updates.items():
                setattr(run, key, value)

    def _start_run_step(self, run_id: UUID, name: str) -> UUID:
        step_id = uuid4()
        with get_session() as session:
            step = models.RunStep(
                id=step_id,
                run_id=run_id,
                name=name,
                status=JobState.RUNNING,
                started_at=datetime.utcnow(),
            )
            session.add(step)
        return step_id

    def _finish_run_step(self, step_id: UUID, status: str, logs: Optional[str] = None) -> None:
        with get_session() as session:
            step = session.get(models.RunStep, step_id)
            if not step:
                return
            step.status = status
            step.finished_at = datetime.utcnow()
            if logs:
                step.logs = logs

    def _run_quick_regen(
        self,
        job: JobStatus,
        options: RunOptions,
        generator: ScopeDocGenerator,
        paths,
        step_callback,
    ) -> str:
        if not options.parent_run_id:
            raise ValueError("Quick regen requires parent_run_id")

        parent_uuid = UUID(options.parent_run_id)

        def emit(step: str, event: str, detail: Optional[str] = None) -> None:
            if step_callback is None:
                return
            try:
                step_callback(step, event, detail)
            except Exception:
                pass

        emit("load_baseline", "started", None)

        with get_session() as session:
            parent_run = session.get(models.Run, parent_uuid)
            if parent_run is None:
                raise ValueError("Parent run not found")
            if str(parent_run.project_id) != job.project_id:
                raise ValueError("Parent run belongs to a different project")
            if parent_run.status != JobState.SUCCESS:
                raise ValueError("Parent run must be successful for quick regeneration")

            variables_artifact = (
                session.query(models.Artifact)
                .filter(
                    models.Artifact.run_id == parent_uuid,
                    models.Artifact.kind == "variables",
                )
                .order_by(models.Artifact.created_at.desc())
                .first()
            )

        if variables_artifact is None:
            raise ValueError("Parent run is missing extracted variables")

        artifact_path = (paths.root / Path(variables_artifact.path)).resolve()
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        if not artifact_path.exists() and self._use_remote_storage:
            key = self._storage_key(job.project_id, variables_artifact.path)
            self._storage.download_to_path(key, artifact_path)

        if not artifact_path.exists():
            raise FileNotFoundError(f"Variables artifact not found at {artifact_path}")

        with artifact_path.open('r', encoding='utf-8') as f:
            baseline_variables = json.load(f)

        emit("load_baseline", "completed", None)

        updated_variables = baseline_variables
        change_request = (options.variables_delta or "").strip()

        if change_request:
            emit("adjust_variables", "started", None)
            try:
                updated_variables = generator.extractor.rewrite_variables(
                    baseline_variables,
                    change_request,
                    generator.variables_schema,
                    generator.variables_guide,
                )
            except Exception as exc:
                emit("adjust_variables", "failed", str(exc))
                raise
            emit("adjust_variables", "completed", None)
        else:
            emit("adjust_variables", "completed", "No changes requested")

        try:
            updated_variables['date_created'] = datetime.utcnow().date().isoformat()
        except Exception:
            pass

        variables_output = generator.output_dir / "extracted_variables.json"
        variables_output.parent.mkdir(parents=True, exist_ok=True)
        with variables_output.open('w', encoding='utf-8') as f:
            json.dump(updated_variables, f, indent=2)

        emit("render", "started", None)
        try:
            rendered_path = generator.generate_from_variables(variables_output)
        except Exception as exc:
            emit("render", "failed", str(exc))
            raise
        output_name = Path(rendered_path).name
        emit("render", "completed", output_name)

        return rendered_path

    def _record_artifacts(
        self,
        run_id: UUID,
        project_id: str,
        paths,
        result_rel: Optional[str],
    ) -> Dict[str, UUID]:
        run_dir = paths.runs_dir / str(run_id)
        run_working_dir = run_dir / "working"
        run_artifacts_dir = run_working_dir / "artifacts"
        run_outputs_dir = run_dir / "outputs"

        entries = []
        context_pack_path = run_artifacts_dir / "context_pack.json"
        if context_pack_path.exists():
            entries.append(("context_pack", context_pack_path, {"type": "json"}))

        variables_path = run_outputs_dir / "extracted_variables.json"
        if variables_path.exists():
            entries.append(("variables", variables_path, {"type": "json"}))

        if result_rel:
            rendered_path = (paths.root / Path(result_rel)).resolve()
            if rendered_path.exists():
                entries.append(("rendered_doc", rendered_path, {"type": "markdown"}))

        # Check for solution graphic images
        import glob
        for img_path in glob.glob(str(run_outputs_dir / "solution_graphic_*")):
            img_file = Path(img_path)
            if img_file.exists():
                ext = img_file.suffix.lower()
                mime = "image/png" if ext == ".png" else "image/jpeg"
                entries.append(("solution_graphic", img_file, {"type": mime}))
                break  # Only take the first/latest one

        created: Dict[str, UUID] = {}
        if not entries:
            return created

        with get_session() as session:
            for kind, abs_path, meta in entries:
                try:
                    relative = str(abs_path.relative_to(paths.root))
                except ValueError:
                    relative = str(abs_path)
                if self._use_remote_storage:
                    self._upload_to_storage(project_id, abs_path)
                artifact = models.Artifact(
                    run_id=run_id,
                    kind=kind,
                    path=relative,
                    meta=meta or {},
                )
                session.add(artifact)
                session.flush()
                created[kind] = artifact.id
        return created

    def _relative_to_project(self, root: Path, path_str: Optional[str]) -> Optional[str]:
        if not path_str:
            return None
        candidate = Path(path_str)
        try:
            return str(candidate.relative_to(root))
        except ValueError:
            return str(candidate)

    # ------------------------------------------------------------------
    # Embeddings (manual trigger only - removed automatic embedding)
    # ------------------------------------------------------------------
    # Embedding is now manually triggered via POST /runs/{run_id}/embed endpoint
    # This ensures consistent compact profile embeddings using extracted variables

    def _get_embedder(self) -> Optional[ProfileEmbedder]:
        if self._embedder is not None:
            return self._embedder
        try:
            self._embedder = ProfileEmbedder(HISTORY_EMBEDDING_MODEL)
        except Exception as exc:
            print(f"[WARN] Vector embedding disabled: {exc}")
            self._embedder = None
        return self._embedder

    # ------------------------------------------------------------------
    # Storage helpers
    # ------------------------------------------------------------------
    def _prepare_workspace(
        self,
        project_id: str,
        paths,
        *,
        included_ids: Optional[List[str]] = None,
    ) -> Tuple[List[str], List[str]]:
        self._clear_directory(paths.input_dir)
        try:
            project_uuid = UUID(project_id)
        except ValueError as exc:
            raise ValueError(f"Invalid project id '{project_id}': {exc}")

        warnings: List[str] = []
        errors: List[str] = []
        with get_session() as session:
            query = (
                session.query(models.ProjectFile)
                .filter(models.ProjectFile.project_id == project_uuid)
            )
            if included_ids:
                try:
                    uuid_list = [UUID(fid) for fid in included_ids]
                except Exception:
                    uuid_list = []
                if uuid_list:
                    query = query.filter(models.ProjectFile.id.in_(uuid_list))
            files = query.all()
        for record in files:
            target = paths.root / record.path
            target.parent.mkdir(parents=True, exist_ok=True)
            
            # Check if we should use summary instead of native file
            if record.use_summary_for_generation and record.is_summarized and record.summary_text:
                # Write summary text to a .summary.txt file instead of downloading native file
                summary_target = target.parent / f"{target.name}.summary.txt"
                try:
                    summary_target.write_text(record.summary_text, encoding="utf-8")
                    LOGGER.info(
                        "Using summary for %s (saved to %s)",
                        record.filename,
                        summary_target.name,
                    )
                except Exception as exc:
                    errors.append(f"Failed to write summary for '{record.filename}': {exc}")
            else:
                # Download native file from storage
                key = self._storage_key(project_id, record.path)
                try:
                    self._storage.download_to_path(key, target)
                except FileNotFoundError:
                    warnings.append(f"Missing in storage: {record.path}")
                except Exception as exc:
                    errors.append(f"Failed to download '{record.path}': {exc}")
        return errors, warnings

    def _clear_directory(self, path: Path) -> None:
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
            return
        for child in path.iterdir():
            if child.is_dir():
                shutil.rmtree(child, ignore_errors=True)
            else:
                try:
                    child.unlink()
                except FileNotFoundError:
                    pass

    def _upload_to_storage(self, project_id: str, local_path: Path) -> None:
        if not local_path.exists() or not local_path.is_file():
            return
        try:
            relative = local_path.relative_to(DATA_ROOT / "projects" / project_id)
        except ValueError:
            relative = local_path.name
        key = self._storage_key(project_id, str(relative))
        try:
            self._storage.upload_file(key, local_path)
        except Exception as exc:
            print(f"[WARN] Failed to upload '{local_path}' to storage: {exc}")

    def _storage_key(self, project_id: str, relative_path: str) -> str:
        clean = relative_path.replace("\\", "/").lstrip("/")
        return f"projects/{project_id}/{clean}"

    def _record_input_file(self, project_id: str, file_path: Path, media_type: str | None = None) -> None:
        if not file_path.exists():
            return
        try:
            project_uuid = UUID(project_id)
        except ValueError:
            return

        try:
            relative = file_path.relative_to(DATA_ROOT / "projects" / project_id)
            relative_path = relative.as_posix()
        except ValueError:
            relative_path = file_path.name

        size = file_path.stat().st_size
        checksum = hashlib.sha256(file_path.read_bytes()).hexdigest()
        if media_type is None:
            media_type = "application/octet-stream"
        with get_session() as session:
            record = (
                session.query(models.ProjectFile)
                .filter(
                    models.ProjectFile.project_id == project_uuid,
                    models.ProjectFile.path == relative_path,
                )
                .one_or_none()
            )
            if record:
                record.filename = file_path.name
                record.size = size
                record.media_type = media_type
                record.checksum = checksum
            else:
                session.add(
                    models.ProjectFile(
                        project_id=project_uuid,
                        filename=file_path.name,
                        path=relative_path,
                        size=size,
                        media_type=media_type,
                        checksum=checksum,
                    )
                )

