"""Vector search endpoint backed by pgvector."""

from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from server.core.config import HISTORY_EMBEDDING_MODEL
from server.core.history_profiles import ProfileEmbedder

from ..services import VectorStore


router = APIRouter(prefix="/search", tags=["search"])

_embedder: Optional[ProfileEmbedder] = None


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=3)
    project_id: Optional[UUID] = None
    top_k: int = Field(5, ge=1, le=20)


class SearchResult(BaseModel):
    embedding_id: UUID
    project_id: Optional[UUID]
    doc_kind: str
    similarity: float
    metadata: dict


class SearchResponse(BaseModel):
    results: List[SearchResult]


def _get_embedder() -> ProfileEmbedder:
    global _embedder
    if _embedder is None:
        _embedder = ProfileEmbedder(HISTORY_EMBEDDING_MODEL)
    return _embedder


@router.post("/", response_model=SearchResponse)
async def search_embeddings(payload: SearchRequest, request: Request) -> SearchResponse:
    store = _get_vector_store(request)
    embedder = _get_embedder()
    embedding_vector = embedder.embed(payload.query)

    project_filter = payload.project_id
    results = store.similarity_search(
        embedding_vector,
        top_k=payload.top_k,
        project_id=project_filter,
    )

    response = [
        SearchResult(
            embedding_id=result.id,
            project_id=result.project_id,
            doc_kind=result.doc_kind,
            similarity=result.similarity,
            metadata=result.metadata,
        )
        for result in results
    ]
    return SearchResponse(results=response)


def _get_vector_store(request: Request) -> VectorStore:
    store = getattr(request.app.state, "vector_store", None)
    if store is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Vector store unavailable")
    return store

