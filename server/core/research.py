"""Research helpers supporting Claude web search and Perplexity."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Iterable, List, Optional

import httpx

from .config import (
    ENABLE_WEB_RESEARCH,
    PERPLEXITY_API_KEY,
    PERPLEXITY_BASE_URL,
    PERPLEXITY_MODEL,
)


logger = logging.getLogger(__name__)


class ResearchMode(str, Enum):
    NONE = "none"
    QUICK = "quick"
    FULL = "full"


@dataclass
class ResearchFinding:
    provider: str
    query: str
    summary: str
    references: List[str]


class PerplexityClient:
    """Minimal Perplexity API wrapper."""

    def __init__(self, api_key: str, *, base_url: str = PERPLEXITY_BASE_URL, model: str = PERPLEXITY_MODEL) -> None:
        if not api_key:
            raise ValueError("Perplexity API key is required for full research mode")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model

    def query(self, prompt: str) -> ResearchFinding:
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "You are a senior solutions architect researching technical feasibility."},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": 800,
            "temperature": 0.2,
            "return_citations": True,
        }

        # Simple retry with backoff for transient errors
        attempt = 0
        last_exc: Exception | None = None
        while attempt < 3:
            try:
                with httpx.Client(timeout=60.0) as client:
                    response = client.post(url, headers=headers, json=payload)
                    response.raise_for_status()
                    data = response.json()
                break
            except (httpx.TimeoutException, httpx.HTTPStatusError) as exc:
                # Log server response text when available for debuggability (e.g., 400 details)
                try:
                    resp = exc.response  # type: ignore[attr-defined]
                    detail = resp.text if resp is not None else str(exc)
                except Exception:
                    detail = str(exc)

                # Only retry on transient errors (429 and 5xx). For 4xx (like 400), do not retry.
                status = getattr(exc, "response", None).status_code if hasattr(exc, "response") and exc.response is not None else None
                transient = status in (429, 500, 502, 503, 504) or isinstance(exc, httpx.TimeoutException)
                if not transient:
                    logger.warning("Perplexity non-retryable error (%s): %s", status, detail)
                    raise

                last_exc = exc
                attempt += 1
                wait = 1.5 ** attempt
                logger.warning("Perplexity retry %s after error (%s): %s", attempt, status, detail)
                try:
                    import time
                    time.sleep(wait)
                except Exception:
                    pass
            except Exception as exc:
                # Non-retryable
                raise

        if last_exc and attempt >= 3:
            raise last_exc

        message = (data.get("choices", [{}])[0] or {}).get("message", {})
        content = message.get("content", "") or ""

        # Collect citations from multiple possible locations
        refs: List[str] = []
        def _collect_citations(obj) -> None:
            items = obj or []
            for item in items:
                if isinstance(item, dict):
                    ref = item.get("url") or item.get("citation")
                    if ref:
                        refs.append(str(ref))
                elif isinstance(item, str):
                    refs.append(item)

        _collect_citations(message.get("citations"))
        _collect_citations(data.get("citations"))

        # De-duplicate while preserving order
        seen = set()
        unique_refs: List[str] = []
        for r in refs:
            if r not in seen:
                seen.add(r)
                unique_refs.append(r)

        return ResearchFinding(
            provider="perplexity",
            query=prompt,
            summary=content.strip(),
            references=unique_refs,
        )


class ResearchManager:
    """Coordinates research behaviour for the generator."""

    def __init__(self, mode: ResearchMode) -> None:
        self.mode = mode
        self.perplexity_client: Optional[PerplexityClient] = None
        if mode is ResearchMode.FULL:
            if not PERPLEXITY_API_KEY:
                logger.warning("PERPLEXITY_API_KEY not set; full research will be skipped")
            else:
                try:
                    self.perplexity_client = PerplexityClient(PERPLEXITY_API_KEY)
                except Exception as exc:  # pragma: no cover - initialization guard
                    logger.warning("Unable to initialize Perplexity client: %s", exc)

    def allows_web_search_tool(self) -> bool:
        if self.mode is ResearchMode.NONE:
            return False
        if self.mode is ResearchMode.QUICK:
            return ENABLE_WEB_RESEARCH
        if self.mode is ResearchMode.FULL:
            return ENABLE_WEB_RESEARCH
        return False

    def gather_research(self, context_pack: dict, project_focus: Optional[str] = None) -> List[ResearchFinding]:
        if self.mode is not ResearchMode.FULL or not self.perplexity_client:
            return []

        queries = self._build_queries(context_pack, project_focus)
        findings: List[ResearchFinding] = []
        for query in queries:
            try:
                finding = self.perplexity_client.query(query)
                findings.append(finding)
            except httpx.HTTPError as http_err:  # pragma: no cover - network guard
                logger.warning("Perplexity request failed for '%s': %s", query, http_err)
            except Exception as exc:  # pragma: no cover - resilience
                logger.warning("Unexpected Perplexity error for '%s': %s", query, exc)
        return findings

    # ----- Post-extraction research -----
    def gather_post_extraction(self, variables: dict) -> List[ResearchFinding]:
        """Use extracted variables to verify service/API assumptions via Perplexity.

        Builds targeted queries from tech_stack, integration_points, and data_sources.
        """
        if self.mode is not ResearchMode.FULL or not self.perplexity_client:
            return []

        queries = self._build_post_queries(variables)
        findings: List[ResearchFinding] = []
        for query in queries:
            try:
                findings.append(self.perplexity_client.query(query))
            except Exception as exc:  # pragma: no cover - network guard
                logger.warning("Perplexity post-extraction query failed: %s", exc)
        return findings

    def _build_post_queries(self, variables: dict) -> List[str]:
        services: List[str] = []

        def _add_service_from_text(text: str) -> None:
            raw = (text or "").strip()
            if not raw:
                return
            # Extract service name before '-' or ':' or ' via '
            for sep in [" - ", " – ", ":", " via "]:
                if sep in raw:
                    raw = raw.split(sep, 1)[0].strip()
                    break
            if raw and raw not in services:
                services.append(raw)

        for item in (variables.get("tech_stack") or []):
            if isinstance(item, str):
                _add_service_from_text(item)
        for item in (variables.get("integration_points") or []):
            if isinstance(item, str):
                _add_service_from_text(item)
        for item in (variables.get("data_sources") or []):
            if isinstance(item, str):
                _add_service_from_text(item)

        # Limit the number of services to keep calls bounded
        services = services[:6]

        queries: List[str] = []
        for svc in services:
            queries.append(
                (
                    f"Verify whether '{svc}' provides an official public API suitable for automation. "
                    f"Provide links to official documentation and note auth requirements (OAuth, API key, service account). "
                    f"If no official API exists, state that clearly and suggest the closest official alternative. "
                    f"Use 1-2 sentences and list 1-3 authoritative references."
                )
            )
        return queries

    def _build_queries(self, context_pack: dict, project_focus: Optional[str]) -> List[str]:
        queries: List[str] = []

        focus = project_focus or "technical scope project"
        pain_points = context_pack.get("pain_points") or []
        integrations = context_pack.get("integration_notes") or []
        unknowns = context_pack.get("unknowns") or []

        if pain_points:
            first = pain_points[0]
            desc = first.get("description") or "key technical pain points"
            queries.append(f"Best practices to address {desc} for {focus}")

        if integrations:
            first = integrations[0]
            note = first.get("note") or "integration challenges"
            queries.append(f"Integration considerations: {note} for {focus}")

        if unknowns:
            first = unknowns[0]
            item = first.get("unknown") or "project unknowns"
            queries.append(f"How to mitigate {item} when planning {focus}")

        if not queries:
            queries.append(f"Key technical considerations for {focus}")

        # Limit to three queries to control token + call volume
        return queries[:3]

