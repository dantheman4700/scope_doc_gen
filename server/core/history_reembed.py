"""Rebuild profile texts and re-embed existing scopes using the current embedder.

Usage:
  python -m server.core.history_reembed --dsn "postgresql://user:pass@host:5432/history" [--embedding-model text-embedding-3-small]
"""

from __future__ import annotations

import json
from typing import Optional
from pathlib import Path

from .config import HISTORY_EMBEDDING_MODEL
from .history_db import HistoryDatabase
from .history_profiles import ProfileEmbedder, build_profile_text


def reembed_all(dsn: str, embedding_model: str) -> None:
    db = HistoryDatabase(dsn)
    embedder = ProfileEmbedder(embedding_model)
    dim = embedder.dim or len(embedder.embed("test"))
    db.ensure_schema(vector_dim=dim)

    with db.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT s.id, s.title, sv.variables
                FROM scopes s
                JOIN scope_variables sv ON sv.scope_id = s.id
                """
            )
            rows = cur.fetchall()

    print(f"[INFO] Re-embedding {len(rows)} scope(s) with model: {embedding_model}")
    for scope_id, title, variables in rows:
        try:
            vars_dict = variables if isinstance(variables, dict) else json.loads(variables)
        except Exception:
            vars_dict = {}
        profile_text = build_profile_text(title, vars_dict, vars_dict.get('services'), vars_dict.get('tags'))
        embedding = embedder.embed(profile_text)
        db.upsert_profile(scope_id, profile_text, embedding, embedder.model_name)
        print(f"[OK] Re-embedded scope: {scope_id} ({title})")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Re-embed scope profiles using the current embedder")
    parser.add_argument("--dsn", required=True, help="PostgreSQL connection string")
    parser.add_argument("--embedding-model", default=HISTORY_EMBEDDING_MODEL, help="Embedding model name")
    args = parser.parse_args()
    reembed_all(args.dsn, args.embedding_model)


if __name__ == "__main__":
    main()


