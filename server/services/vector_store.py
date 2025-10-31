"""Postgres + pgvector backed vector store helper."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Iterable, Optional, Sequence
from uuid import UUID, uuid4

import psycopg
from pgvector.psycopg import Vector, register_vector
from psycopg.rows import dict_row


logger = logging.getLogger(__name__)


class VectorStoreError(RuntimeError):
    """Raised when vector store operations fail."""


@dataclass
class VectorRecord:
    id: UUID
    project_id: Optional[UUID]
    doc_kind: str
    similarity: float
    metadata: dict
    created_at: str


class VectorStore:
    """Thin wrapper around pgvector operations."""

    def __init__(self, dsn: str, *, embedding_dim: int = 1536) -> None:
        if not dsn:
            raise ValueError("VectorStore requires a valid DATABASE_DSN")
        self.dsn = dsn
        self.embedding_dim = embedding_dim

    def _connect(self):
        conn = psycopg.connect(self.dsn, row_factory=dict_row)
        register_vector(conn)
        return conn

    # ------------------------------------------------------------------
    # Schema helpers
    # ------------------------------------------------------------------
    def ensure_schema(self) -> None:
        """Create required tables and indexes if they do not exist."""

        statements = [
            "CREATE EXTENSION IF NOT EXISTS vector",
            f"""
            CREATE TABLE IF NOT EXISTS scope_embeddings (
                id UUID PRIMARY KEY,
                project_id UUID,
                doc_kind TEXT NOT NULL,
                embedding vector({self.embedding_dim}) NOT NULL,
                metadata JSONB,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_scope_embeddings_project
                ON scope_embeddings (project_id)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_scope_embeddings_embedding
                ON scope_embeddings USING ivfflat (embedding vector_cosine_ops)
                WITH (lists = 100)
            """,
        ]

        with self._connect() as conn, conn.cursor() as cur:
            for i, stmt in enumerate(statements, 1):
                try:
                    logger.debug(f"Executing schema statement {i}/{len(statements)}")
                    cur.execute(stmt)
                    conn.commit()
                except Exception as exc:
                    conn.rollback()
                    # Log which statement failed
                    logger.error(f"Failed to execute schema statement {i}: {stmt[:100]}...")
                    raise VectorStoreError(f"Failed to execute schema statement: {exc}") from exc

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------
    def upsert_embedding(
        self,
        *,
        embedding: Sequence[float],
        project_id: Optional[UUID],
        doc_kind: str,
        metadata: Optional[dict] = None,
        embedding_id: Optional[UUID] = None,
    ) -> UUID:
        """Insert or update an embedding record."""

        embedding_id = embedding_id or uuid4()

        with self._connect() as conn, conn.cursor() as cur:
            try:
                cur.execute(
                    """
                    INSERT INTO scope_embeddings (id, project_id, doc_kind, embedding, metadata)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE
                        SET project_id = EXCLUDED.project_id,
                            doc_kind = EXCLUDED.doc_kind,
                            embedding = EXCLUDED.embedding,
                            metadata = EXCLUDED.metadata,
                            created_at = NOW()
                    """,
                    (
                        embedding_id,
                        project_id,
                        doc_kind,
                        Vector(list(embedding)),
                        metadata,
                    ),
                )
            except Exception as exc:
                conn.rollback()
                raise VectorStoreError(f"Failed to upsert embedding: {exc}") from exc
            else:
                conn.commit()

        return embedding_id

    def delete_embeddings(self, embedding_ids: Iterable[UUID]) -> int:
        ids = list(embedding_ids)
        if not ids:
            return 0
        with self._connect() as conn, conn.cursor() as cur:
            try:
                cur.execute(
                    "DELETE FROM scope_embeddings WHERE id = ANY(%s)",
                    (ids,),
                )
                deleted = cur.rowcount
            except Exception as exc:
                conn.rollback()
                raise VectorStoreError(f"Failed to delete embeddings: {exc}") from exc
            else:
                conn.commit()
        return deleted

    def similarity_search(
        self,
        embedding: Sequence[float],
        *,
        top_k: int = 5,
        project_id: Optional[UUID] = None,
    ) -> list[VectorRecord]:
        """Return nearest neighbours using cosine distance."""

        query = [
            "SELECT id, project_id, doc_kind, metadata, created_at,",
            "       embedding <=> %s AS similarity",
            "FROM scope_embeddings",
        ]
        params: list = [Vector(list(embedding))]

        if project_id:
            query.append("WHERE project_id = %s")
            params.append(project_id)

        query.append("ORDER BY embedding <=> %s ASC LIMIT %s")
        params.append(Vector(list(embedding)))
        params.append(top_k)

        sql = "\n".join(query)

        with self._connect() as conn, conn.cursor() as cur:
            try:
                cur.execute(sql, params)
                rows = cur.fetchall()
            except Exception as exc:
                raise VectorStoreError(f"Similarity search failed: {exc}") from exc

        results: list[VectorRecord] = []
        for row in rows:
            results.append(
                VectorRecord(
                    id=row["id"],
                    project_id=row.get("project_id"),
                    doc_kind=row["doc_kind"],
                    similarity=row["similarity"],
                    metadata=row.get("metadata") or {},
                    created_at=str(row["created_at"]),
                )
            )
        return results

