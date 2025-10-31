"""FastAPI application factory and global middleware registration."""

from __future__ import annotations

from typing import Dict

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from server.core.config import (
    CORS_ALLOW_CREDENTIALS,
    CORS_ALLOW_ORIGINS,
    DATABASE_DSN,
    HISTORY_EMBEDDING_MODEL,
    VECTOR_STORE_DSN,
)
from server.core.history_profiles import EMBED_DIMENSIONS

from .routes import (
    auth_router,
    projects_router,
    files_router,
    runs_router,
    run_detail_router,
    embeddings_router,
    artifacts_router,
    search_router,
    system_router,
)
from .services import VectorStore, VectorStoreError, JobRegistry


def _attach_vector_store(app: FastAPI) -> None:
    """Initialise the pgvector-backed store if configured."""

    if not VECTOR_STORE_DSN:
        return

    try:
        embedding_dim = EMBED_DIMENSIONS.get(HISTORY_EMBEDDING_MODEL, 1536)
        store = VectorStore(VECTOR_STORE_DSN, embedding_dim=embedding_dim)
        store.ensure_schema()
        app.state.vector_store = store
    except Exception as exc:  # pragma: no cover - logging path
        app.state.vector_store = None
        detail = exc if isinstance(exc, VectorStoreError) else str(exc)
        print(f"[WARN] Vector store unavailable: {detail}")


def _attach_job_registry(app: FastAPI) -> None:
    vector_store = getattr(app.state, "vector_store", None)
    app.state.job_registry = JobRegistry(vector_store=vector_store)


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""

    app = FastAPI(
        title="Scope Doc Generator API",
        version="0.1.0",
        description="Backend services for the scope document generator platform.",
    )

    # CORS configuration (placeholder defaults; tighten once frontend origin is known)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ALLOW_ORIGINS,
        allow_credentials=CORS_ALLOW_CREDENTIALS,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routers
    app.include_router(auth_router)
    app.include_router(projects_router)
    app.include_router(files_router)
    app.include_router(runs_router)
    app.include_router(run_detail_router)
    app.include_router(embeddings_router)
    app.include_router(artifacts_router)
    app.include_router(search_router)
    app.include_router(system_router)

    _attach_vector_store(app)
    _attach_job_registry(app)

    return app


app = create_app()


@app.get("/health", tags=["system"])
async def healthcheck() -> Dict[str, str]:
    """Simple healthcheck endpoint for orchestration probes."""

    return {"status": "ok"}

