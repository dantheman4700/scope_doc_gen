"""Per-file summarization with evidence and caching."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .config import OUTPUT_DIR, MAX_TOKENS, TEMPERATURE
from .llm import ClaudeExtractor


@dataclass
class FileSummary:
    filename: str
    summary: Dict[str, Any]
    cache_path: Optional[Path] = None


class FileSummarizer:
    """Creates structured, decision-oriented summaries with evidence quotes per file.

    Uses the existing ClaudeExtractor client for API calls and robust backoff.
    Caches summaries by content hash to avoid reprocessing unchanged files.
    """

    def __init__(self, extractor: ClaudeExtractor, cache_root: Optional[Path] = None) -> None:
        self.extractor = extractor
        self.cache_root = (cache_root or (OUTPUT_DIR / "artifacts" / "summaries")).resolve()
        self.cache_root.mkdir(parents=True, exist_ok=True)

    def summarize_file(
        self,
        filename: str,
        content: str,
        project_focus: Optional[str] = None,
        file_note: Optional[str] = None,
    ) -> FileSummary:
        doc_stub = {
            "filename": filename,
            "content": content,
            "path": None,
            "media_type": "text/plain",
            "source_type": "text",
            "size_bytes": len(content.encode("utf-8", errors="ignore")),
            "upload_via": "text",
            "can_upload": False,
            "content_hash": self._hash_text(content),
        }
        return self.summarize_document(
            document=doc_stub,
            project_focus=project_focus,
            file_note=file_note,
        )

    def summarize_document(
        self,
        document: Dict[str, Any],
        project_focus: Optional[str] = None,
        file_note: Optional[str] = None,
    ) -> FileSummary:
        filename = document.get("filename", "unknown")
        content = document.get("content", "")
        cache_key = self._make_cache_key(
            filename,
            content,
            project_focus,
            file_note,
            document.get("content_hash"),
        )
        cache_path = self.cache_root / f"{self._sanitize_name(filename)}.{cache_key}.json"
        if cache_path.exists():
            try:
                with open(cache_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                return FileSummary(filename=filename, summary=data, cache_path=cache_path)
            except Exception:
                pass

        prompt = self._build_prompt(document, project_focus, file_note)
        message_content = self._build_message_content(document, prompt)

        # Exponential backoff for rate limits/errors
        attempt = 0
        while True:
            try:
                response = self.extractor.client.messages.create(
                    model=self.extractor.model,
                    max_tokens=min(4000, MAX_TOKENS),
                    temperature=max(0.1, TEMPERATURE),
                    system=self._system_instructions(),
                    messages=[{"role": "user", "content": message_content}],
                )
                text = response.content[0].text
                summary = self._parse_json(text)

                with open(cache_path, 'w', encoding='utf-8') as f:
                    json.dump(summary, f, indent=2)
                return FileSummary(filename=filename, summary=summary, cache_path=cache_path)

            except Exception as e:
                msg = str(e)
                if 'rate_limit' in msg or '429' in msg:
                    wait = min(20, 5 * (2 ** attempt))
                    print(f"[WARN] Rate limit while summarizing {filename}. Retrying in {wait}s (attempt {attempt+1})")
                    time.sleep(wait)
                    attempt += 1
                    if attempt >= 3:
                        print(f"[ERROR] Failed to summarize {filename} due to repeated rate limits; returning minimal stub")
                        return FileSummary(filename=filename, summary=self._minimal_stub(filename), cache_path=None)
                    continue
                else:
                    print(f"[ERROR] Failed to summarize {filename}: {e}")
                    return FileSummary(filename=filename, summary=self._minimal_stub(filename), cache_path=None)

    def _system_instructions(self) -> str:
        return (
            "You are a senior solutions architect. Summarize files for technical scope planning. "
            "Produce strictly valid JSON matching the schema instructed. Preserve key evidence via quotes."
        )

    def _build_prompt(
        self,
        document: Dict[str, Any],
        project_focus: Optional[str],
        file_note: Optional[str],
    ) -> str:
        filename = document.get("filename", "unknown")
        content = document.get("content", "")
        schema = {
            "filename": "string",
            "purpose": "string",
            "key_entities": ["string"],
            "pain_points": [
                {"description": "string", "severity": "low|medium|high", "evidence_refs": ["int"]}
            ],
            "risks": ["string"],
            "integration_complexity": "string",
            "unknowns": ["string"],
            "effort_multipliers": ["string"],
            "must_read_sections": ["string"],
            "evidence_quotes": [
                {"quote": "string", "rationale": "string", "approx_location": "string"}
            ],
            "importance_score": 0,
        }

        header = []
        if project_focus:
            header.append(f"PROJECT FOCUS: {project_focus}")
        header.append(f"SOURCE FILE: {filename}")
        if file_note:
            header.append(f"FILE NOTE: {file_note}")
        upload_via = document.get("upload_via")
        source_type = document.get("source_type")
        if upload_via and source_type:
            header.append(f"SOURCE TYPE: {source_type}; INGEST METHOD: {upload_via}")
        if document.get("page_count"):
            header.append(f"PAGE COUNT: {document['page_count']}")
        if document.get("can_upload") and upload_via == 'attachment':
            header.append("NOTE: Original file provided via native upload in this message.")
        elif upload_via == 'ocr':
            header.append("NOTE: Content obtained via OCR from the original file.")
        elif upload_via == 'skipped':
            header.append("WARNING: File exceeded upload limits; only placeholder content available.")

        return (
            "\n".join(header)
            + "\n\nGOAL: Create a decision-oriented summary for scope planning.\n"
            + "Focus on: pain points, risks, integration complexity, unknowns, and what increases effort.\n"
            + "Include 3-10 evidence quotes from the content with brief rationale and approximate location.\n"
            + "Return strictly valid JSON matching this schema (and nothing else):\n"
            + json.dumps(schema, indent=2)
            + "\n\nCONTENT:\n"
            + content
        )

    def _build_message_content(self, document: Dict[str, Any], prompt: str) -> List[Dict[str, Any]]:
        blocks: List[Dict[str, Any]] = []

        if document.get("can_upload") and document.get("upload_via") == 'attachment':
            path = document.get("path")
            media_type = document.get("media_type", "application/octet-stream")
            if path:
                try:
                    data_b64 = self._encode_base64(Path(path))
                    attachment_type = 'document'
                    if media_type.startswith('image/'):
                        attachment_type = 'image'
                    blocks.append({
                        "type": attachment_type,
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": data_b64,
                        },
                    })
                except Exception as exc:
                    print(f"[WARN] Could not attach file {document.get('filename')}: {exc}")

        blocks.append({"type": "text", "text": prompt})
        return blocks

    def _encode_base64(self, path: Path) -> str:
        with open(path, 'rb') as f:
            return base64.standard_b64encode(f.read()).decode('utf-8')

    def _hash_text(self, text: str) -> str:
        hasher = hashlib.sha256()
        hasher.update(text.encode('utf-8', errors='ignore'))
        return hasher.hexdigest()

    def _parse_json(self, text: str) -> Dict[str, Any]:
        t = text.strip()
        if t.startswith('{') and t.endswith('}'):
            return json.loads(t)
        fence = t.find("```json")
        if fence != -1:
            fence_end = t.find("```", fence + 7)
            if fence_end != -1:
                return json.loads(t[fence + 7:fence_end].strip())
        start = t.find('{')
        end = t.rfind('}')
        if start != -1 and end != -1 and end > start:
            return json.loads(t[start:end + 1])
        # Fallback minimal
        return self._minimal_stub("unknown")

    def _minimal_stub(self, filename: str) -> Dict[str, Any]:
        return {
            "filename": filename,
            "purpose": "",
            "key_entities": [],
            "pain_points": [],
            "risks": [],
            "integration_complexity": "",
            "unknowns": [],
            "effort_multipliers": [],
            "must_read_sections": [],
            "evidence_quotes": [],
            "importance_score": 0,
        }

    def _make_cache_key(
        self,
        filename: str,
        content: str,
        project_focus: Optional[str],
        file_note: Optional[str],
        content_hash: Optional[str] = None,
    ) -> str:
        h = hashlib.sha256()
        h.update(filename.encode('utf-8', errors='ignore'))
        h.update(content.encode('utf-8', errors='ignore'))
        if project_focus:
            h.update(project_focus.encode('utf-8', errors='ignore'))
        if file_note:
            h.update(file_note.encode('utf-8', errors='ignore'))
        if content_hash:
            h.update(content_hash.encode('utf-8', errors='ignore'))
        return h.hexdigest()[:16]

    def _sanitize_name(self, name: str) -> str:
        return "".join(c if c.isalnum() or c in ('.','-','_') else '_' for c in name)


