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
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "You are a senior solutions architect researching technical feasibility."},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": 800,
            "temperature": 0.2,
        }
        with httpx.Client(timeout=30.0) as client:
            response = client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

        message = data.get("choices", [{}])[0].get("message", {})
        content = message.get("content", "") or ""
        citations = message.get("citations") or []
        # Some responses may include citations field; ensure string list
        refs: List[str] = []
        for item in citations:
            if isinstance(item, dict):
                ref = item.get("url") or item.get("citation")
                if ref:
                    refs.append(str(ref))
            elif isinstance(item, str):
                refs.append(item)

        return ResearchFinding(
            provider="perplexity",
            query=prompt,
            summary=content.strip(),
            references=refs,
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

