"""Project storage helpers.

These utilities encapsulate the on-disk layout for project data. They are
responsible for creating the expected directory structure inside the shared
``DATA_ROOT`` (configured elsewhere) and returning strongly-typed handles that
the rest of the application can rely on.

Layout (per project)::

    DATA_ROOT/
        projects/
            <project_id>/
                input/
                working/
                    combined/
                    artifacts/
                    cache/
                        summaries/
                outputs/
                runs/

Future tasks may add more subdirectories (e.g., per-run folders or upload
staging). Keeping the logic in one place makes that evolution easier.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable


class ProjectStorageError(RuntimeError):
    """Raised when project storage operations fail."""


@dataclass(frozen=True)
class ProjectPaths:
    """Represents all filesystem locations for a single project."""

    project_id: str
    root: Path
    input_dir: Path
    working_dir: Path
    outputs_dir: Path
    runs_dir: Path
    combined_dir: Path
    artifacts_dir: Path
    cache_dir: Path
    summaries_cache_dir: Path

    def as_dict(self) -> Dict[str, str]:
        """Return a JSON-serialisable view of the paths."""

        return {
            "project_id": self.project_id,
            "root": str(self.root),
            "input_dir": str(self.input_dir),
            "working_dir": str(self.working_dir),
            "outputs_dir": str(self.outputs_dir),
            "runs_dir": str(self.runs_dir),
            "combined_dir": str(self.combined_dir),
            "artifacts_dir": str(self.artifacts_dir),
            "cache_dir": str(self.cache_dir),
            "summaries_cache_dir": str(self.summaries_cache_dir),
        }


def _assert_safe_project_id(project_id: str) -> str:
    normalised = project_id.strip()
    if not normalised:
        raise ProjectStorageError("project_id cannot be empty")
    if any(sep in normalised for sep in ("/", "\\")):
        raise ProjectStorageError("project_id must not contain path separators")
    if normalised in {".", ".."}:
        raise ProjectStorageError("project_id cannot be '.' or '..'")
    return normalised


def _mkdir_all(paths: Iterable[Path]) -> None:
    for path in paths:
        path.mkdir(parents=True, exist_ok=True)


def ensure_data_root(data_root: Path) -> Path:
    """Guarantee that the ``DATA_ROOT`` base directory exists."""

    projects_dir = data_root / "projects"
    _mkdir_all((projects_dir,))
    return projects_dir


def get_project_paths(data_root: Path, project_id: str) -> ProjectPaths:
    """Return project paths without mutating the filesystem."""

    safe_id = _assert_safe_project_id(project_id)
    root = data_root / "projects" / safe_id
    working_dir = root / "working"
    cache_dir = working_dir / "cache"
    summaries_cache_dir = cache_dir / "summaries"
    return ProjectPaths(
        project_id=safe_id,
        root=root,
        input_dir=root / "input",
        working_dir=working_dir,
        outputs_dir=root / "outputs",
        runs_dir=root / "runs",
        combined_dir=working_dir / "combined",
        artifacts_dir=working_dir / "artifacts",
        cache_dir=cache_dir,
        summaries_cache_dir=summaries_cache_dir,
    )


def ensure_project_structure(data_root: Path, project_id: str) -> ProjectPaths:
    """Ensure that the project directory tree exists and return its paths."""

    paths = get_project_paths(data_root, project_id)
    ensure_data_root(data_root)
    required_paths = (
        paths.root,
        paths.input_dir,
        paths.working_dir,
        paths.outputs_dir,
        paths.runs_dir,
        paths.combined_dir,
        paths.artifacts_dir,
        paths.cache_dir,
        paths.summaries_cache_dir,
    )
    _mkdir_all(required_paths)
    return paths

