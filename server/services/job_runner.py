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
    HISTORY_EMBEDDING_MODEL,
    STORAGE_PROVIDER,
)
from server.core.history_profiles import ProfileEmbedder

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
        }


@dataclass
class JobStatus:
    id: UUID
    project_id: str
    run_mode: str
    research_mode: str
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
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "result_path": self.result_path,
            "error": self.error,
            "params": self.params,
        }


class JobRegistry:
    """In-memory job tracker backed by a thread pool executor."""

    def __init__(self, max_workers: int = 2, *, vector_store: Optional[VectorStore] = None) -> None:
        self._jobs: Dict[UUID, JobStatus] = {}
        self._lock = Lock()
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._vector_store = vector_store
        self._embedder: Optional[ProfileEmbedder] = None
        self._storage = get_storage()
        self._use_remote_storage = STORAGE_PROVIDER == "supabase"

    def create_job(self, project_id: str, options: RunOptions) -> JobStatus:
        job_id = uuid4()
        job = JobStatus(
            id=job_id,
            project_id=project_id,
            run_mode=options.run_mode,
            research_mode=options.research_mode,
            params=options.to_dict(),
        )

        with self._lock:
            self._jobs[job_id] = job

        self._ensure_run_record(job, options)
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

    def _ensure_run_record(self, job: JobStatus, options: RunOptions) -> None:
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
        sync_step_id = self._start_run_step(job.id, "sync inputs")
        try:
            sync_errors, sync_warnings = self._prepare_workspace(
                job.project_id,
                paths,
                included_ids=options.included_file_ids,
            )
        except Exception as exc:  # pragma: no cover - defensive
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

        try:
            generator = ScopeDocGenerator(
                input_dir=paths.input_dir,
                output_dir=paths.outputs_dir,
                project_dir=paths.root,
            )

            if options.parent_run_id:
                result_path = self._run_quick_regen(job, options, generator, paths, step_callback)
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
            result_rel = self._relative_to_project(paths.root, result_path)
            if self._use_remote_storage and result_rel:
                self._upload_to_storage(job.project_id, paths.root / Path(result_rel))
            self._mark_success(job, result_rel)
            self._update_run(job.id, status=JobState.SUCCESS, finished_at=datetime.utcnow(), result_path=result_rel)
            artifact_ids = self._record_artifacts(job.id, job.project_id, paths, result_rel)
            variables_artifact_id = artifact_ids.get("variables")
            if variables_artifact_id:
                self._update_run(job.id, extracted_variables_artifact_id=variables_artifact_id)
                job.params.setdefault("extracted_variables_artifact_id", str(variables_artifact_id))
            self._record_embedding(job, paths, result_rel, options)
        except Exception as exc:  # pragma: no cover - execution safeguard
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
        entries = []
        context_pack_path = paths.artifacts_dir / "context_pack.json"
        if context_pack_path.exists():
            entries.append(("context_pack", context_pack_path, {"type": "json"}))

        variables_path = paths.outputs_dir / "extracted_variables.json"
        if variables_path.exists():
            entries.append(("variables", variables_path, {"type": "json"}))

        if result_rel:
            rendered_path = (paths.root / Path(result_rel)).resolve()
            if rendered_path.exists():
                entries.append(("rendered_doc", rendered_path, {"type": "markdown"}))

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
    # Embeddings
    # ------------------------------------------------------------------
    def _record_embedding(self, job: JobStatus, paths, result_rel: Optional[str], options: RunOptions) -> None:
        if not options.enable_vector_store:
            return
        if self._vector_store is None:
            return
        embedder = self._get_embedder()
        if embedder is None:
            return
        if not result_rel:
            return

        rendered_path = (paths.root / Path(result_rel)).resolve()
        if not rendered_path.exists() or not rendered_path.is_file():
            return

        try:
            content = rendered_path.read_text(encoding="utf-8")
        except Exception as exc:
            print(f"[WARN] Unable to read rendered document for embedding: {exc}")
            return

        try:
            vector = list(embedder.embed(content))
        except Exception as exc:
            print(f"[WARN] Failed to generate embedding: {exc}")
            return

        try:
            project_uuid = None
            try:
                project_uuid = UUID(job.project_id)
            except Exception:
                project_uuid = None

            metadata = {
                "project_id": job.project_id,
                "run_id": str(job.id),
                "path": str(result_rel),
                "mode": job.run_mode,
                "research_mode": job.research_mode,
            }
            self._vector_store.upsert_embedding(
                embedding=vector,
                project_id=project_uuid,
                doc_kind="rendered_scope",
                metadata=metadata,
            )
        except Exception as exc:
            print(f"[WARN] Failed to store embedding: {exc}")

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

