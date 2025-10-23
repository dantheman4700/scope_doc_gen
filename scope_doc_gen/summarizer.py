"""Per-file summarization with evidence and caching."""

from __future__ import annotations

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

    def __init__(self, extractor: ClaudeExtractor) -> None:
        self.extractor = extractor
        self.cache_root = OUTPUT_DIR / "artifacts" / "summaries"
        self.cache_root.mkdir(parents=True, exist_ok=True)

    def summarize_file(
        self,
        filename: str,
        content: str,
        project_focus: Optional[str] = None,
        file_note: Optional[str] = None,
    ) -> FileSummary:
        cache_key = self._make_cache_key(filename, content, project_focus, file_note)
        cache_path = self.cache_root / f"{self._sanitize_name(filename)}.{cache_key}.json"
        if cache_path.exists():
            try:
                with open(cache_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                return FileSummary(filename=filename, summary=data, cache_path=cache_path)
            except Exception:
                pass

        prompt = self._build_prompt(filename, content, project_focus, file_note)

        # Exponential backoff for rate limits/errors
        attempt = 0
        while True:
            try:
                response = self.extractor.client.messages.create(
                    model=self.extractor.model,
                    max_tokens=min(4000, MAX_TOKENS),
                    temperature=max(0.1, TEMPERATURE),
                    system=self._system_instructions(),
                    messages=[{"role": "user", "content": prompt}],
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
        filename: str,
        content: str,
        project_focus: Optional[str],
        file_note: Optional[str],
    ) -> str:
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
        self, filename: str, content: str, project_focus: Optional[str], file_note: Optional[str]
    ) -> str:
        h = hashlib.sha256()
        h.update(filename.encode('utf-8', errors='ignore'))
        h.update(content.encode('utf-8', errors='ignore'))
        if project_focus:
            h.update(project_focus.encode('utf-8', errors='ignore'))
        if file_note:
            h.update(file_note.encode('utf-8', errors='ignore'))
        return h.hexdigest()[:16]

    def _sanitize_name(self, name: str) -> str:
        return "".join(c if c.isalnum() or c in ('.','-','_') else '_' for c in name)


