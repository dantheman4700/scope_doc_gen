"""Import legacy scope documents into the main vector store.

This CLI scans a directory of historical scopes (pdf/docx/md/txt),
extracts variables with Claude, builds a compact profile text, embeds
with the configured model, and upserts into the app's pgvector store
(`scope_embeddings`).
"""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Optional
from uuid import UUID

from .config import HISTORY_EMBEDDING_MODEL, VECTOR_STORE_DSN
from .history_profiles import ProfileEmbedder, build_profile_text
from .ingest import DocumentIngester
from .llm import ClaudeExtractor
from ..services.vector_store import VectorStore


SUPPORTED_IMPORT_SUFFIXES = {".pdf", ".md", ".txt", ".docx", ".doc"}

# Extraction schema and prompt for historical scope import
EXTRACTION_SYSTEM_PROMPT = """
You are an expert analyst cataloging past automation scope documents. Extract key estimation
signals and project descriptors. Return ONLY valid JSON matching the schema provided.
Do not add explanations, markdown code fences, or extra commentary.

Assume a standard development labor rate of $200/hour for any development-related effort or when inferring cost implications from hours, unless the source document explicitly specifies a different rate.
"""

EXTRACTION_SCHEMA = {
    "client_name": "string",
    "project_name": "string",
    "project_summary": "string",
    "project_type": "string",
    "industry": "string",
    "services": ["string"],
    "automation_scope": "string",
    "high_level_workflow": "string",
    "technology_stack": ["string"],
    "key_integrations": ["string"],
    "automation_outputs": ["string"],
    "hours_total": "number",
    "hours_by_role": [{"role": "string", "hours": "number"}],
    "dev_hours": "number",
    "training_hours": "number",
    "pm_hours": "number",
    "other_hours": [{"label": "string", "hours": "number"}],
    "timeline_weeks": "number",
    "milestone_count": "integer",
    "milestones": [{"name": "string", "week": "number", "description": "string"}],
    "total_setup_cost": "number",
    "monthly_operating_cost": "number",
    "current_process_cost_breakdown": [{"label": "string", "amount": "number"}],
    "automation_benefits_breakdown": [{"label": "string", "amount": "number"}],
    "tags": ["string"],
}


def _parse_json_response(text: str) -> dict:
    """Parse JSON from Claude response, handling code fences and other formatting."""
    cleaned = text.strip()
    if cleaned.startswith("{") and cleaned.endswith("}"):
        return json.loads(cleaned)
    fence = cleaned.find("```json")
    if fence != -1:
        fence_end = cleaned.find("```", fence + 7)
        if fence_end != -1:
            return json.loads(cleaned[fence + 7:fence_end].strip())
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        return json.loads(cleaned[start:end + 1])
    raise ValueError("No JSON object found in Claude response")


def extract_variables_from_scope(
    content: str,
    extractor: ClaudeExtractor,
    attachment: dict | None = None,
) -> dict:
    """Extract structured variables from a historical scope document using Claude."""
    user_prompt = (
        "Analyze the historical scope document (attached and/or included below) and extract the required fields.\n"
        "Return JSON matching this schema (types indicate the expected value type):\n"
        f"{json.dumps(EXTRACTION_SCHEMA, indent=2)}"
    )

    message_content = []
    if attachment:
        message_content.append(attachment)
    message_content.append({"type": "text", "text": user_prompt})
    message_content.append({"type": "text", "text": "DOCUMENT CONTENT:\n" + content})

    response = extractor.client.messages.create(
        model=extractor.model,
        max_tokens=2000,
        temperature=0.1,
        system=EXTRACTION_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": message_content}],
    )
    text = response.content[0].text
    data = _parse_json_response(text)
    if not isinstance(data, dict):
        raise ValueError("Extraction response was not a JSON object")
    return data


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

        # Store metadata in same flat structure as live system for consistency
        metadata = {
            "import_source": "legacy_directory_import",
            "filename": path.name,
            "source_path": str(path.resolve()),
            "profile_text": profile_text,
            "title": (variables or {}).get("project_name") or path.stem,
            "hours_total": (variables or {}).get("hours_total"),
            "timeline_weeks": (variables or {}).get("timeline_weeks"),
            "milestone_count": (variables or {}).get("milestone_count") or len((variables or {}).get("milestones", [])),
            "services": (variables or {}).get("services"),
            "tags": (variables or {}).get("tags"),
            "dev_hours": (variables or {}).get("dev_hours"),
            "training_hours": (variables or {}).get("training_hours"),
            "pm_hours": (variables or {}).get("pm_hours"),
            "total_setup_cost": (variables or {}).get("total_setup_cost"),
            "monthly_operating_cost": (variables or {}).get("monthly_operating_cost"),
            "automation_outputs": (variables or {}).get("automation_outputs"),
            "client_name": (variables or {}).get("client_name"),
            "project_name": (variables or {}).get("project_name"),
            "industry": (variables or {}).get("industry"),
            "project_type": (variables or {}).get("project_type"),
        }

        try:
            store.upsert_embedding(
                embedding=vector,
                project_id=project_uuid,  # None for global historical scopes
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


