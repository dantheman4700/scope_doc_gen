"""Postgres + pgvector backed vector store helper."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Iterable, Optional, Sequence
from uuid import UUID, uuid4
from contextlib import contextmanager

from pgvector.psycopg import Vector, register_vector
from psycopg.types.json import Json
from sqlalchemy.engine import Engine


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
    """Thin wrapper around pgvector operations using SQLAlchemy connection pool.
    
    All operations use the same database connection pool as the rest of the application,
    ensuring consistent connection management and avoiding connection exhaustion.
    """

    def __init__(
        self,
        engine: Engine,
        *,
        embedding_dim: int = 1536,
    ) -> None:
        """
        Initialize VectorStore.
        
        Args:
            engine: SQLAlchemy Engine (must be provided - uses shared connection pool)
            embedding_dim: Dimension of embedding vectors
        """
        if not isinstance(engine, Engine):
            raise ValueError("VectorStore requires a SQLAlchemy Engine instance")
        
        self.engine = engine
        self.embedding_dim = embedding_dim
        self._schema_ensured = False  # Track if schema has been created
        logger.info("VectorStore initialized using SQLAlchemy connection pool (shared with app)")

    @contextmanager
    def _connect(self):
        """Get a connection from SQLAlchemy pool with vector support registered.
        
        Uses the same connection pool as all other database operations in the application.
        """
        conn = None
        try:
            # Get raw psycopg connection from SQLAlchemy pool
            # This uses the same pool as SQLAlchemy ORM operations
            conn = self.engine.raw_connection()
            register_vector(conn)  # Enable pgvector support
            yield conn
        except Exception:
            # If connection is bad, close it
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass
            raise
        finally:
            # Return connection to SQLAlchemy pool
            # raw_connection() returns a proxy that handles cleanup automatically
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass

    # ------------------------------------------------------------------
    # Schema helpers
    # ------------------------------------------------------------------
    def _ensure_schema_lazy(self) -> None:
        """Lazily ensure schema is created - only once, on first use."""
        if self._schema_ensured:
            return
        
        try:
            self.ensure_schema()
            self._schema_ensured = True
        except Exception as exc:
            # Log but don't fail - schema might already exist from another worker
            logger.warning(f"Schema initialization failed (may already exist): {exc}")
            # Mark as ensured anyway to avoid repeated attempts
            self._schema_ensured = True

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

        with self._connect() as conn:
            with conn.cursor() as cur:
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
        self._ensure_schema_lazy()  # Lazy schema creation

        embedding_id = embedding_id or uuid4()

        with self._connect() as conn:
            with conn.cursor() as cur:
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
                            Json(metadata) if metadata else None,
                        ),
                    )
                except Exception as exc:
                    conn.rollback()
                    raise VectorStoreError(f"Failed to upsert embedding: {exc}") from exc
                else:
                    conn.commit()

        return embedding_id

    def delete_embeddings(self, embedding_ids: Iterable[UUID]) -> int:
        self._ensure_schema_lazy()  # Lazy schema creation
        ids = list(embedding_ids)
        if not ids:
            return 0
        with self._connect() as conn:
            with conn.cursor() as cur:
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
        self._ensure_schema_lazy()  # Lazy schema creation

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

        with self._connect() as conn:
            with conn.cursor() as cur:
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

