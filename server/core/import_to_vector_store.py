"""Import legacy scope documents into the main vector store.

This CLI scans a directory of historical scopes (pdf/docx/md/txt),
extracts variables with Claude, builds a compact profile text, embeds
with the configured model, and upserts into the app's pgvector store
(`scope_embeddings`).
"""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Optional
from uuid import UUID

from .config import HISTORY_EMBEDDING_MODEL, VECTOR_STORE_DSN
from .history_profiles import ProfileEmbedder, build_profile_text
from .ingest import DocumentIngester
from .llm import ClaudeExtractor
from .history_import import extract_variables_from_scope
from ..services.vector_store import VectorStore


SUPPORTED_IMPORT_SUFFIXES = {".pdf", ".md", ".txt", ".docx", ".doc"}


def _build_attachment_block(doc: dict) -> Optional[dict]:
    """Optionally include a native document block for better extraction accuracy.

    For PDFs/DOCX that are reasonably sized, we attach as a Claude document block
    (base64). DOC/DOCX are converted to PDF when possible.
    """
    try:
        if doc.get("upload_via") != "attachment" or not doc.get("path"):
            return None

        src_path = Path(doc["path"]) if doc.get("path") else None
        if not src_path or not src_path.exists():
            return None

        media_type = doc.get("media_type", "application/pdf")

        # Convert DOC/DOCX to PDF for Claude document blocks when possible
        if src_path.suffix.lower() in {".docx", ".doc"}:
            try:
                tmp_pdf = src_path.with_suffix(".converted.pdf")
                from docx2pdf import convert as _docx2pdf  # type: ignore

                _docx2pdf(str(src_path), str(tmp_pdf))
                src_path = tmp_pdf
                media_type = "application/pdf"
            except Exception:
                # Fall back to text-only if conversion unavailable
                return None

        if media_type != "application/pdf":
            return None

        with open(src_path, "rb") as f:
            data_b64 = base64.b64encode(f.read()).decode("utf-8")

        return {
            "type": "document",
            "source": {
                "type": "base64",
                "media_type": media_type,
                "data": data_b64,
            },
        }
    except Exception:
        return None


def import_directory_to_vector_store(
    directory: Path,
    *,
    project_id: Optional[str] = None,
    doc_kind: str = "historical_scope",
    embedding_model: Optional[str] = None,
    vector_store_dsn: Optional[str] = None,
) -> None:
    """Import all supported files under `directory` into the main vector store.

    - Extracts variables using Claude for each file
    - Builds a compact profile text
    - Embeds with OpenAI (model from config unless overridden)
    - Upserts into `scope_embeddings` with helpful metadata
    """

    vector_dsn = vector_store_dsn or VECTOR_STORE_DSN
    if not vector_dsn:
        raise RuntimeError("VECTOR_STORE_DSN is not configured; set DATABASE_DSN in your environment")

    model_name = embedding_model or HISTORY_EMBEDDING_MODEL
    embedder = ProfileEmbedder(model_name)
    extractor = ClaudeExtractor()

    store = VectorStore(vector_dsn, embedding_dim=embedder.dim or 1536)
    store.ensure_schema()

    ingester = DocumentIngester()

    project_uuid: Optional[UUID] = None
    if project_id:
        try:
            project_uuid = UUID(project_id)
        except Exception:
            project_uuid = None

    for path in directory.glob("**/*"):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_IMPORT_SUFFIXES:
            continue

        print(f"[IMPORT] {path}")
        try:
            doc = ingester.ingest_file(path)
        except Exception as exc:
            print(f"[WARN] Unable to ingest: {path} ({exc})")
            continue

        # Consolidate text content across chunked docs
        if isinstance(doc, list):
            content = "\n\n".join(d.get("content", "") for d in doc if isinstance(d, dict))
            attachment_block = None
        else:
            content = (doc or {}).get("content", "")
            attachment_block = _build_attachment_block(doc or {})

        if not content:
            print(f"[SKIP] No extractable text: {path}")
            continue

        # Extract variables with Claude to build a compact, comparable profile
        try:
            variables = extract_variables_from_scope(content, extractor, attachment_block)
        except Exception as exc:
            print(f"[WARN] Variable extraction failed, falling back to raw text embed: {exc}")
            variables = None

        profile_text = (
            build_profile_text(
                title=path.stem,
                variables=variables or {"project_type": "automation_scope"},
                services=(variables or {}).get("services"),
                tags=(variables or {}).get("tags"),
            )
            if variables
            else (content[:12000])
        )

        # Generate embedding and upsert into the vector store
        try:
            vector = list(embedder.embed(profile_text))
        except Exception as exc:
            print(f"[WARN] Embedding failed: {path} ({exc})")
            continue

        metadata = {
            "import_source": "legacy_directory_import",
            "filename": path.name,
            "path": str(path.resolve()),
            "variables": variables or None,
            "profile_text_preview": profile_text[:500],
        }

        try:
            store.upsert_embedding(
                embedding=vector,
                project_id=project_uuid,
                doc_kind=doc_kind,
                metadata=metadata,
            )
            print("[OK] Embedded:", path.name)
        except Exception as exc:
            print(f"[WARN] Failed to store embedding for {path}: {exc}")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Import legacy scopes into the app's vector store")
    parser.add_argument("directory", type=Path, help="Directory containing historical scopes (pdf/docx/md/txt)")
    parser.add_argument("--project-id", type=str, default=None, help="Optional project UUID to associate embeddings")
    parser.add_argument("--doc-kind", type=str, default="historical_scope", help="doc_kind to label imported embeddings")
    parser.add_argument("--embedding-model", type=str, default=None, help="Embedding model (default: config HISTORY_EMBEDDING_MODEL)")
    parser.add_argument("--dsn", type=str, default=None, help="Override vector store DSN (default: config VECTOR_STORE_DSN)")

    args = parser.parse_args()
    import_directory_to_vector_store(
        args.directory,
        project_id=args.project_id,
        doc_kind=args.doc_kind,
        embedding_model=args.embedding_model,
        vector_store_dsn=args.dsn,
    )


if __name__ == "__main__":
    main()


