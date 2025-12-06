"""Postgres + pgvector backed vector store helper."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Iterable, Optional, Sequence
from uuid import UUID, uuid4
from contextlib import contextmanager

import psycopg
from pgvector.psycopg import Vector, register_vector
from psycopg.rows import dict_row
from psycopg.types.json import Json
from psycopg_pool import ConnectionPool


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
    """Thin wrapper around pgvector operations with connection pooling."""

    def __init__(self, dsn: str, *, embedding_dim: int = 1536) -> None:
        if not dsn:
            raise ValueError("VectorStore requires a valid DATABASE_DSN")
        self.dsn = dsn
        self.embedding_dim = embedding_dim
        self._schema_ensured = False  # Track if schema has been created
        
        # Create a connection pool for VectorStore operations
        # LAZY initialization (min_size=0) to avoid exhausting Supabase on startup
        # Pool size: 0 min (lazy), 2 max - very conservative for Supabase Session mode
        # These connections are separate from SQLAlchemy pool
        try:
            self._pool = ConnectionPool(
                self.dsn,
                min_size=0,  # LAZY - don't create connections until needed
                max_size=4,  # Reasonable max for vector operations
                max_waiting=10,
                max_idle=300,  # 5 minutes
                reconnect_timeout=30,
                kwargs={"row_factory": dict_row},
            )
            logger.info("VectorStore connection pool initialized (min=0, max=4, lazy)")
        except Exception as exc:
            logger.error(f"Failed to create VectorStore connection pool: {exc}")
            raise VectorStoreError(f"Connection pool initialization failed: {exc}") from exc

    def __del__(self):
        """Clean up connection pool on destruction."""
        if hasattr(self, "_pool"):
            try:
                self._pool.close()
            except Exception:
                pass  # Ignore errors during cleanup

    @contextmanager
    def _connect(self):
        """Get a connection from the pool with vector support registered."""
        conn = None
        try:
            conn = self._pool.getconn()
            register_vector(conn)
            yield conn
        except Exception:
            # If connection is bad, close it instead of returning to pool
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass
            raise
        finally:
            # Only return connection to pool if it's still open and valid
            if conn is not None:
                try:
                    # Check if connection is still open before returning
                    if not conn.closed:
                        self._pool.putconn(conn)
                    # If closed, don't return to pool - it will be replaced automatically
                except Exception:
                    # If putconn fails, connection is likely bad - don't return it
                    # The pool will create a new connection when needed
                    try:
                        if not conn.closed:
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

