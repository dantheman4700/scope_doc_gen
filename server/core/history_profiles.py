"""Embedding utilities and profile builder for historical scopes."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Iterable, Optional

import os
from openai import OpenAI


EMBED_DIMENSIONS = {
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
}


class ProfileEmbedder:
    """Embedding helper backed by OpenAI embedding models."""

    def __init__(self, model_name: str, api_key: Optional[str] = None) -> None:
        self.model_name = model_name
        self.dim = EMBED_DIMENSIONS.get(model_name)
        self._client: Optional[OpenAI] = None
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")

    @property
    def client(self) -> OpenAI:
        if self._client is None:
            if not self.api_key:
                raise ValueError("OPENAI_API_KEY not set; required for history embeddings")
            self._client = OpenAI(api_key=self.api_key)
        return self._client

    def embed(self, text: str) -> Iterable[float]:
        response = self.client.embeddings.create(
            model=self.model_name,
            input=text,
        )
        return response.data[0].embedding


def hash_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def build_profile_text(
    title: Optional[str],
    variables: dict,
    services: Optional[Iterable[str]] = None,
    tags: Optional[Iterable[str]] = None,
) -> str:
    """Build a compact, token-only profile optimized for vector search.

    Format (examples):
      industry:flooring | project_type:quotation_automation | services:quoting,invoicing | integrations:quickbooks,buildertrend | outputs:proposal,pdf | hours:180 | weeks:6 | tags:construction
    """
    tokens: list[str] = []

    industry = variables.get('industry')
    if industry:
        tokens.append(f"industry:{str(industry).strip()}")

    project_type = variables.get('project_type') or variables.get('solution_type')
    if project_type:
        tokens.append(f"project_type:{str(project_type).strip()}")

    stack = variables.get('technology_stack') or variables.get('integrations')
    if stack:
        if isinstance(stack, list):
            tokens.append("integrations:" + ",".join(str(x).strip() for x in stack if x))
        else:
            tokens.append("integrations:" + str(stack).strip())

    outputs = variables.get('automation_outputs')
    if outputs:
        if isinstance(outputs, list):
            tokens.append("outputs:" + ",".join(str(x).strip() for x in outputs if x))
        else:
            tokens.append("outputs:" + str(outputs).strip())

    hours = variables.get('hours_total') or variables.get('estimated_hours')
    if hours is not None:
        try:
            tokens.append(f"hours:{float(hours):.0f}")
        except Exception:
            tokens.append(f"hours:{hours}")

    weeks = variables.get('timeline_weeks') or variables.get('project_timeline_weeks')
    if weeks is not None:
        try:
            tokens.append(f"weeks:{float(weeks):.0f}")
        except Exception:
            tokens.append(f"weeks:{weeks}")

    if services:
        tokens.append("services:" + ",".join(str(x).strip() for x in services if x))

    if tags:
        tokens.append("tags:" + ",".join(str(x).strip() for x in tags if x))

    return " | ".join(tokens)

