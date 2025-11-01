"""Utilities for counting tokens via the Claude API."""

from __future__ import annotations

import base64
import logging
from typing import Iterable, Mapping

import httpx

from server.core.config import ANTHROPIC_API_KEY, CLAUDE_MODEL


LOGGER = logging.getLogger(__name__)

ANTHROPIC_VERSION = "2023-06-01"
COUNT_TOKENS_URL = "https://api.anthropic.com/v1/messages/count_tokens"


class TokenCountingError(RuntimeError):
    """Raised when the Claude token counting API fails."""


def make_text_block(text: str) -> Mapping[str, str]:
    """Create a token counting block for plain text."""

    return {"type": "text", "text": text}


def make_document_block(
    *,
    data: bytes,
    media_type: str,
    filename: str | None = None,
) -> Mapping[str, object]:
    """Create a token counting block for a binary document.
    
    Note: The 'name' field is NOT included because the token counting API
    does not accept it (returns 400 error). The filename parameter is kept
    for API compatibility but is not used in the token counting context.
    """

    encoded = base64.b64encode(data).decode("ascii")
    return {
        "type": "document",
        "source": {
            "type": "base64",
            "media_type": media_type,
            "data": encoded,
        },
    }


def make_image_block(*, data: bytes, media_type: str) -> Mapping[str, object]:
    """Create a token counting block for an image."""

    encoded = base64.b64encode(data).decode("ascii")
    return {
        "type": "image",
        "source": {
            "type": "base64",
            "media_type": media_type,
            "data": encoded,
        },
    }


async def count_tokens_for_blocks(blocks: Iterable[Mapping[str, object]]) -> int:
    """Use the Claude API to count tokens for a sequence of content blocks."""

    if not ANTHROPIC_API_KEY:
        raise TokenCountingError("ANTHROPIC_API_KEY is not configured")

    message = {
        "role": "user",
        "content": list(blocks),
    }

    headers = {
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": ANTHROPIC_VERSION,
        "content-type": "application/json",
    }

    payload = {
        "model": CLAUDE_MODEL,
        "messages": [message],
    }

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=10.0)) as client:
            response = await client.post(COUNT_TOKENS_URL, headers=headers, json=payload)
    except httpx.HTTPError as exc:
        LOGGER.error("Token counting request failed: %s", exc)
        raise TokenCountingError("Token counting request failed") from exc

    if response.status_code >= 400:
        LOGGER.error(
            "Token counting API returned %s: %s",
            response.status_code,
            response.text,
        )
        raise TokenCountingError(
            f"Token counting API error: {response.status_code}"
        )

    try:
        data = response.json()
    except ValueError as exc:
        LOGGER.error("Invalid JSON in token count response: %s", response.text)
        raise TokenCountingError("Invalid JSON from token count API") from exc

    tokens = data.get("input_tokens")
    if not isinstance(tokens, int):
        LOGGER.error("Token count missing or invalid: %s", data)
        raise TokenCountingError("Token count missing in response")

    return tokens

