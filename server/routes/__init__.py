"""API routers for the FastAPI backend."""

from .auth import router as auth_router
from .projects import router as projects_router
from .files import router as files_router
from .runs import router as runs_router, run_router as run_detail_router
from .embeddings import router as embeddings_router
from .artifacts import router as artifacts_router
from .search import router as search_router
from .system import router as system_router

__all__ = [
    "auth_router",
    "projects_router",
    "files_router",
    "runs_router",
    "embeddings_router",
    "artifacts_router",
    "search_router",
    "system_router",
    "run_detail_router",
]

