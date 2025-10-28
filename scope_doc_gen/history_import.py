"""CLI utility to import historical scopes into the retrieval database."""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Iterable, Optional

from .config import HISTORY_EMBEDDING_MODEL
from .history_db import HistoryDatabase
from .history_profiles import ProfileEmbedder, build_profile_text, hash_file
from .ingest import DocumentIngester
from .llm import ClaudeExtractor


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


def _safe_float(value) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def _safe_int(value) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    try:
        return int(float(str(value)))
    except (TypeError, ValueError):
        return None


def _ensure_list(value) -> Optional[list]:
    if value is None:
        return None
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        return [value]
    return None


def _ensure_struct_list(value) -> Optional[list]:
    if value is None:
        return None
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        return [value]
    return None


def import_scope_file(
    path: Path,
    history_db: HistoryDatabase,
    embedder: ProfileEmbedder,
    extractor: ClaudeExtractor,
) -> None:
    scope_id = hash_file(path)
    # Skip duplicates by content hash
    if history_db.scope_exists(scope_id):
        print(f"[SKIP] Already imported: {path}")
        return

    ingester = DocumentIngester()
    doc = ingester.ingest_file(path)
    if not doc:
        print(f"[WARN] Unable to ingest historical scope: {path}")
        return

    attachment_block = None
    if isinstance(doc, list):
        content = "\n\n".join(d.get('content', '') for d in doc if d)
    else:
        content = doc.get('content', '')
        if doc.get('upload_via') == 'attachment' and doc.get('path'):
            try:
                src_path = Path(doc['path'])
                media_type = doc.get('media_type', 'application/pdf')
                # Convert DOC/DOCX to PDF for upload, as Claude requires application/pdf for document blocks
                if src_path.suffix.lower() in {'.docx', '.doc'}:
                    try:
                        tmp_pdf = src_path.with_suffix('.converted.pdf')
                        from docx2pdf import convert as _docx2pdf
                        _docx2pdf(str(src_path), str(tmp_pdf))
                        src_path = tmp_pdf
                        media_type = 'application/pdf'
                    except Exception as conv_exc:
                        print(f"[WARN] DOCX->PDF conversion failed, sending text only: {conv_exc}")
                        media_type = None

                if media_type == 'application/pdf':
                    with open(src_path, 'rb') as f:
                        data_b64 = base64.b64encode(f.read()).decode('utf-8')
                    attachment_block = {
                        "type": "document",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": data_b64,
                        },
                    }
            except Exception as exc:
                print(f"[WARN] Could not attach original file for {path}: {exc}")

    if not content:
        print(f"[WARN] Historical scope had no extractable content: {path}")
        return
    try:
        variables = extract_variables_from_scope(content, extractor, attachment_block)
    except Exception as exc:
        print(f"[WARN] Extraction failed for {path}: {exc}")
        return

    profile_text = build_profile_text(
        title=path.stem,
        variables=variables,
        services=_ensure_list(variables.get('services')),
        tags=_ensure_list(variables.get('tags')),
    )
    embedding = embedder.embed(profile_text)

    history_db.upsert_scope(
        scope_id,
        title=path.stem,
        source_path=str(path),
        content_sha=scope_id,
        model_name=embedder.model_name,
        client_name=variables.get('client_name'),
        project_name=variables.get('project_name'),
        industry=variables.get('industry'),
        project_type=variables.get('project_type'),
    )
    history_db.upsert_variables(
        scope_id,
        variables=variables,
        hours_total=_safe_float(variables.get('hours_total')),
        timeline_weeks=_safe_float(variables.get('timeline_weeks')),
        milestone_count=_safe_int(variables.get('milestone_count')),
        services=_ensure_list(variables.get('services')),
        tags=_ensure_list(variables.get('tags')),
        hours_by_role=_ensure_struct_list(variables.get('hours_by_role')),
        dev_hours=_safe_float(variables.get('dev_hours')),
        training_hours=_safe_float(variables.get('training_hours')),
        pm_hours=_safe_float(variables.get('pm_hours')),
        total_setup_cost=_safe_float(variables.get('total_setup_cost')),
        monthly_operating_cost=_safe_float(variables.get('monthly_operating_cost')),
        automation_outputs=_ensure_list(variables.get('automation_outputs')),
        client_name=variables.get('client_name'),
        project_name=variables.get('project_name'),
        industry=variables.get('industry'),
        project_type=variables.get('project_type'),
        current_process_cost_breakdown=_ensure_struct_list(variables.get('current_process_cost_breakdown')),
        automation_benefits_breakdown=_ensure_struct_list(variables.get('automation_benefits_breakdown')),
    )
    history_db.upsert_profile(scope_id, profile_text, embedding, embedder.model_name)
    print(f"[OK] Imported historical scope: {path}")


def import_directory(
    directory: Path,
    dsn: str,
    embedding_model: str,
) -> None:
    history_db = HistoryDatabase(dsn)
    embedder = ProfileEmbedder(embedding_model)
    extractor = ClaudeExtractor()
    dim = embedder.dim or len(embedder.embed("test"))
    history_db.ensure_schema(vector_dim=dim)

    for path in directory.glob("**/*"):
        if path.is_file() and path.suffix.lower() in {'.pdf', '.md', '.txt', '.docx', '.doc'}:
            import_scope_file(path, history_db, embedder, extractor)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Import historical scope documents for retrieval")
    parser.add_argument("directory", type=Path, help="Directory containing historical scopes (pdf/md/txt)")
    parser.add_argument("--dsn", required=True, help="PostgreSQL connection string")
    parser.add_argument(
        "--embedding-model",
        default=HISTORY_EMBEDDING_MODEL,
        help="SentenceTransformer model name",
    )

    args = parser.parse_args()
    import_directory(args.directory, args.dsn, args.embedding_model)


if __name__ == "__main__":
    main()

