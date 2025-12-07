"""FastAPI application factory and global middleware registration."""

from __future__ import annotations

import logging
from typing import Dict

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from server.core.config import (
    CORS_ALLOW_CREDENTIALS,
    CORS_ALLOW_ORIGINS,
    DATABASE_DSN,
    HISTORY_EMBEDDING_MODEL,
    VECTOR_STORE_DSN,
)
from server.core.history_profiles import EMBED_DIMENSIONS
from server.db.session import engine

from .routes import (
    auth_router,
    projects_router,
    files_router,
    runs_router,
    run_detail_router,
    embeddings_router,
    artifacts_router,
    system_router,
    teams_router,
    google_router,
)
from .services import VectorStore, VectorStoreError, JobRegistry

# Basic logging config (stdout) if not already configured by the host.
if not logging.getLogger().handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

logger = logging.getLogger("scope.api")


def _attach_vector_store(app: FastAPI) -> None:
    """Initialise the pgvector-backed store if configured."""

    if not DATABASE_DSN:
        logger.info("Vector store not configured (no DATABASE_DSN)")
        app.state.vector_store = None
        return

    try:
        embedding_dim = EMBED_DIMENSIONS.get(HISTORY_EMBEDDING_MODEL, 1536)
        logger.info("Initializing vector store with dimension %s (using SQLAlchemy pool)", embedding_dim)
        # Use SQLAlchemy engine - shares connection pool with rest of app
        store = VectorStore(engine, embedding_dim=embedding_dim)
        # Don't call ensure_schema() at startup - it forces connection creation
        # Schema will be created lazily on first use
        app.state.vector_store = store
        logger.info("Vector store initialized successfully (schema will be created on first use)")
    except Exception as exc:  # pragma: no cover - logging path
        app.state.vector_store = None
        detail = exc if isinstance(exc, VectorStoreError) else str(exc)
        logger.exception("Vector store unavailable: %s", detail)


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
    app.include_router(system_router)
    app.include_router(teams_router)
    app.include_router(google_router)

    _attach_vector_store(app)
    _attach_job_registry(app)

    @app.on_event("shutdown")
    async def shutdown_event():
        """Clean up resources on application shutdown."""
        # VectorStore uses SQLAlchemy engine pool, which is managed by the engine
        # No cleanup needed here
        pass

    @app.middleware("http")
    async def error_logging_middleware(request: Request, call_next):
        try:
            response = await call_next(request)
            return response
        except Exception:
            logger.exception("Unhandled exception during request")
            raise

    return app


app = create_app()


@app.get("/health", tags=["system"])
async def healthcheck() -> Dict[str, str]:
    """Simple healthcheck endpoint for orchestration probes."""

    return {"status": "ok"}

