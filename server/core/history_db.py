"""PostgreSQL storage and retrieval for historical scope profiles."""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterable, List, Optional

import psycopg
from psycopg.types.json import Json


DEFAULT_VECTOR_DIM = 768


class HistoryDatabase:
    """Thin wrapper around psycopg connections for history storage."""

    def __init__(self, dsn: str) -> None:
        self.dsn = dsn

    @contextmanager
    def connection(self):
        conn = psycopg.connect(self.dsn, autocommit=True)
        try:
            yield conn
        finally:
            conn.close()

    def ensure_schema(self, vector_dim: int = DEFAULT_VECTOR_DIM) -> None:
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS scopes (
                        id TEXT PRIMARY KEY,
                        title TEXT,
                        source_path TEXT,
                        created_at TIMESTAMPTZ DEFAULT NOW(),
                        content_sha TEXT,
                        embedding_model TEXT,
                        client_name TEXT,
                        project_name TEXT,
                        industry TEXT,
                        project_type TEXT
                    )
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS scope_variables (
                        scope_id TEXT REFERENCES scopes(id) ON DELETE CASCADE,
                        variables JSONB,
                        hours_total NUMERIC,
                        timeline_weeks INTEGER,
                        milestone_count INTEGER,
                        services TEXT[],
                        tags TEXT[],
                        hours_by_role JSONB,
                        dev_hours NUMERIC,
                        training_hours NUMERIC,
                        pm_hours NUMERIC,
                        total_setup_cost NUMERIC,
                        monthly_operating_cost NUMERIC,
                        automation_outputs TEXT[],
                        current_process_cost_breakdown JSONB,
                        automation_benefits_breakdown JSONB,
                        client_name TEXT,
                        project_name TEXT,
                        industry TEXT,
                        project_type TEXT,
                        extracted_at TIMESTAMPTZ DEFAULT NOW(),
                        PRIMARY KEY (scope_id)
                    )
                    """
                )
                # Ensure columns exist if table created previously
                for ddl in [
                    "ALTER TABLE scopes ADD COLUMN IF NOT EXISTS embedding_model TEXT",
                    "ALTER TABLE scopes ADD COLUMN IF NOT EXISTS client_name TEXT",
                    "ALTER TABLE scopes ADD COLUMN IF NOT EXISTS project_name TEXT",
                    "ALTER TABLE scopes ADD COLUMN IF NOT EXISTS industry TEXT",
                    "ALTER TABLE scopes ADD COLUMN IF NOT EXISTS project_type TEXT",
                    "ALTER TABLE scope_variables ADD COLUMN IF NOT EXISTS hours_by_role JSONB",
                    "ALTER TABLE scope_variables ADD COLUMN IF NOT EXISTS dev_hours NUMERIC",
                    "ALTER TABLE scope_variables ADD COLUMN IF NOT EXISTS training_hours NUMERIC",
                    "ALTER TABLE scope_variables ADD COLUMN IF NOT EXISTS pm_hours NUMERIC",
                    "ALTER TABLE scope_variables ADD COLUMN IF NOT EXISTS total_setup_cost NUMERIC",
                    "ALTER TABLE scope_variables ADD COLUMN IF NOT EXISTS monthly_operating_cost NUMERIC",
                    "ALTER TABLE scope_variables ADD COLUMN IF NOT EXISTS automation_outputs TEXT[]",
                    "ALTER TABLE scope_variables ADD COLUMN IF NOT EXISTS current_process_cost_breakdown JSONB",
                    "ALTER TABLE scope_variables ADD COLUMN IF NOT EXISTS automation_benefits_breakdown JSONB",
                    "ALTER TABLE scope_variables ADD COLUMN IF NOT EXISTS client_name TEXT",
                    "ALTER TABLE scope_variables ADD COLUMN IF NOT EXISTS project_name TEXT",
                    "ALTER TABLE scope_variables ADD COLUMN IF NOT EXISTS industry TEXT",
                    "ALTER TABLE scope_variables ADD COLUMN IF NOT EXISTS project_type TEXT",
                ]:
                    cur.execute(ddl)
                cur.execute(
                    f"""
                    CREATE TABLE IF NOT EXISTS scope_profiles (
                        scope_id TEXT REFERENCES scopes(id) ON DELETE CASCADE,
                        profile_text TEXT,
                        embedding VECTOR({vector_dim}),
                        model TEXT,
                        PRIMARY KEY (scope_id)
                    )
                    """
                )
                # Ensure a cosine index exists for OpenAI embeddings
                cur.execute(
                    "CREATE INDEX IF NOT EXISTS idx_scope_profiles_embedding_cos ON scope_profiles USING hnsw (embedding vector_cosine_ops)"
                )

    def scope_exists(self, scope_id: str) -> bool:
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM scopes WHERE id = %s LIMIT 1", (scope_id,))
                row = cur.fetchone()
                return row is not None

    def upsert_scope(
        self,
        scope_id: str,
        title: Optional[str],
        source_path: Optional[str],
        content_sha: str,
        model_name: Optional[str],
        client_name: Optional[str],
        project_name: Optional[str],
        industry: Optional[str],
        project_type: Optional[str],
    ) -> None:
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO scopes (id, title, source_path, content_sha, embedding_model, client_name, project_name, industry, project_type)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id)
                    DO UPDATE SET title = EXCLUDED.title,
                                   source_path = EXCLUDED.source_path,
                                   content_sha = EXCLUDED.content_sha,
                                   embedding_model = EXCLUDED.embedding_model,
                                   client_name = EXCLUDED.client_name,
                                   project_name = EXCLUDED.project_name,
                                   industry = EXCLUDED.industry,
                                   project_type = EXCLUDED.project_type
                    """,
                    (scope_id, title, source_path, content_sha, model_name, client_name, project_name, industry, project_type),
                )

    def upsert_variables(
        self,
        scope_id: str,
        variables: dict,
        hours_total: Optional[float],
        timeline_weeks: Optional[int],
        milestone_count: Optional[int],
        services: Optional[Iterable[str]],
        tags: Optional[Iterable[str]],
        hours_by_role: Optional[List[dict]],
        dev_hours: Optional[float],
        training_hours: Optional[float],
        pm_hours: Optional[float],
        total_setup_cost: Optional[float],
        monthly_operating_cost: Optional[float],
        automation_outputs: Optional[Iterable[str]],
        current_process_cost_breakdown: Optional[List[dict]],
        automation_benefits_breakdown: Optional[List[dict]],
        client_name: Optional[str],
        project_name: Optional[str],
        industry: Optional[str],
        project_type: Optional[str],
    ) -> None:
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO scope_variables (
                        scope_id, variables, hours_total, timeline_weeks,
                        milestone_count, services, tags, hours_by_role,
                        dev_hours, training_hours, pm_hours,
                        total_setup_cost, monthly_operating_cost,
                        automation_outputs, current_process_cost_breakdown,
                        automation_benefits_breakdown,
                        client_name, project_name,
                        industry, project_type
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (scope_id)
                    DO UPDATE SET variables = EXCLUDED.variables,
                                   hours_total = EXCLUDED.hours_total,
                                   timeline_weeks = EXCLUDED.timeline_weeks,
                                   milestone_count = EXCLUDED.milestone_count,
                                   services = EXCLUDED.services,
                                   tags = EXCLUDED.tags,
                                   hours_by_role = EXCLUDED.hours_by_role,
                                   dev_hours = EXCLUDED.dev_hours,
                                   training_hours = EXCLUDED.training_hours,
                                   pm_hours = EXCLUDED.pm_hours,
                                   total_setup_cost = EXCLUDED.total_setup_cost,
                                   monthly_operating_cost = EXCLUDED.monthly_operating_cost,
                                   automation_outputs = EXCLUDED.automation_outputs,
                                   current_process_cost_breakdown = EXCLUDED.current_process_cost_breakdown,
                                   automation_benefits_breakdown = EXCLUDED.automation_benefits_breakdown,
                                   client_name = EXCLUDED.client_name,
                                   project_name = EXCLUDED.project_name,
                                   industry = EXCLUDED.industry,
                                   project_type = EXCLUDED.project_type,
                                   extracted_at = NOW()
                    """,
                    (
                        scope_id,
                        Json(variables),
                        hours_total,
                        timeline_weeks,
                        milestone_count,
                        list(services) if services else None,
                        list(tags) if tags else None,
                        Json(hours_by_role) if hours_by_role else None,
                        dev_hours,
                        training_hours,
                        pm_hours,
                        total_setup_cost,
                        monthly_operating_cost,
                        list(automation_outputs) if automation_outputs else None,
                        Json(current_process_cost_breakdown) if current_process_cost_breakdown else None,
                        Json(automation_benefits_breakdown) if automation_benefits_breakdown else None,
                        client_name,
                        project_name,
                        industry,
                        project_type,
                    ),
                )

    def upsert_profile(
        self,
        scope_id: str,
        profile_text: str,
        embedding: Iterable[float],
        model: str,
    ) -> None:
        vector = list(embedding)
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO scope_profiles (scope_id, profile_text, embedding, model)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (scope_id)
                    DO UPDATE SET profile_text = EXCLUDED.profile_text,
                                   embedding = EXCLUDED.embedding,
                                   model = EXCLUDED.model
                    """,
                    (
                        scope_id,
                        profile_text,
                        vector,
                        model,
                    ),
                )

    def fetch_similar_profiles(
        self,
        embedding: Iterable[float],
        top_n: int = 12,
        min_similarity: float = 0.2,
    ) -> List[dict]:
        # pgvector expects a vector literal like "[0.1,0.2,0.3]"
        vector = "[" + ",".join(str(float(x)) for x in embedding) + "]"
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT sp.scope_id, sp.profile_text, sp.embedding <-> %s::vector AS distance,
                           sv.hours_total, sv.timeline_weeks, sv.milestone_count,
                           sv.services, sv.tags,
                           sv.dev_hours, sv.training_hours, sv.pm_hours,
                           sv.total_setup_cost, sv.monthly_operating_cost,
                           sv.automation_outputs, sv.client_name, sv.project_name,
                           sv.industry, sv.project_type, s.title
                    FROM scope_profiles sp
                    LEFT JOIN scope_variables sv ON sv.scope_id = sp.scope_id
                    LEFT JOIN scopes s ON s.id = sp.scope_id
                    ORDER BY sp.embedding <-> %s::vector
                    LIMIT %s
                    """,
                    (vector, vector, top_n),
                )
                rows = cur.fetchall()
        results = []
        for row in rows:
            distance = row[2]
            similarity = 1 - distance if distance is not None else None
            results.append(
                {
                    "scope_id": row[0],
                    "profile_text": row[1],
                    "distance": distance,
                    "similarity": similarity,
                    "hours_total": row[3],
                    "timeline_weeks": row[4],
                    "milestone_count": row[5],
                    "services": row[6],
                    "tags": row[7],
                    "dev_hours": row[8],
                    "training_hours": row[9],
                    "pm_hours": row[10],
                    "total_setup_cost": row[11],
                    "monthly_operating_cost": row[12],
                    "automation_outputs": row[13],
                    "client_name": row[14],
                    "project_name": row[15],
                    "industry": row[16],
                    "project_type": row[17],
                    "title": row[18],
                }
            )
        return results

