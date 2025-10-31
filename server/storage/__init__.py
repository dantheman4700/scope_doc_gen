"""Helpers for managing on-disk project storage."""

from .projects import (
    ProjectPaths,
    ensure_data_root,
    ensure_project_structure,
    get_project_paths,
)

__all__ = [
    "ProjectPaths",
    "ensure_data_root",
    "ensure_project_structure",
    "get_project_paths",
]

