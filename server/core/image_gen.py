"""Gemini image generation for scope document graphics (Nano Banana Pro)."""

from __future__ import annotations

import base64
import logging
from dataclasses import dataclass
from typing import Optional

from .config import GEMINI_API_KEY, GEMINI_IMAGE_SIZE

logger = logging.getLogger(__name__)

# Optional dependency - graceful fallback if not installed
try:
    from google import genai
    from google.genai import types as genai_types
    GENAI_AVAILABLE = True
except ImportError:
    genai = None  # type: ignore
    genai_types = None  # type: ignore
    GENAI_AVAILABLE = False
    logger.info("google-genai not installed; image generation disabled")


class ImageGenError(Exception):
    """Raised when image generation fails."""
    pass


@dataclass
class ImageResult:
    """Result of an image generation request."""
    data: bytes
    mime_type: str


# Placeholder prompts - user will provide actual prompts later
SCOPE_IMAGE_PROMPT = """
Create a professional, modern infographic that visualizes this software solution architecture.
Use a clean, corporate design with blues and grays. Show the key components, data flows, and integrations.
The image should be clear and readable at 4K resolution.

Proposed solution:
{solution_text}
"""

PSO_IMAGE_PROMPT = """
Create a professional comparison matrix image showing different solution options side-by-side.
Use a clean, corporate design with a table or grid layout comparing features, costs, and timelines.
The image should be clear and readable at 4K resolution.

Solution options:
{solutions_text}
"""


def _ensure_client(api_key: Optional[str] = None) -> "genai.Client":
    """Get or create a Gemini client."""
    if not GENAI_AVAILABLE:
        raise ImageGenError("google-genai is not installed. Install with: pip install google-genai")
    
    key = api_key or GEMINI_API_KEY
    if not key:
        raise ImageGenError("GEMINI_API_KEY is not configured")
    
    return genai.Client(api_key=key)


def generate_image(
    prompt: str,
    *,
    size: Optional[str] = None,
    api_key: Optional[str] = None,
) -> ImageResult:
    """
    Generate an image using Gemini's image generation model.
    
    Args:
        prompt: The text prompt describing the desired image
        size: Image size (default from config or "1024x1024")
        api_key: Optional API key override
    
    Returns:
        ImageResult with raw bytes and mime type
    
    Raises:
        ImageGenError: If generation fails
    """
    client = _ensure_client(api_key)
    target_size = size or GEMINI_IMAGE_SIZE or "1024x1024"
    
    logger.info(f"Generating image with Gemini (size={target_size})")
    
    try:
        contents = [
            genai_types.Content(
                role="user",
                parts=[genai_types.Part.from_text(text=prompt)],
            )
        ]
        
        config = genai_types.GenerateContentConfig(
            response_modalities=["IMAGE"],
        )
        
        # Use streaming to handle large responses
        response = client.models.generate_content(
            model="gemini-2.0-flash-preview-image-generation",
            contents=contents,
            config=config,
        )
        
        # Extract image from response
        if not response.candidates:
            raise ImageGenError("No candidates in Gemini response")
        
        candidate = response.candidates[0]
        if not candidate.content or not candidate.content.parts:
            raise ImageGenError("No content parts in Gemini response")
        
        for part in candidate.content.parts:
            inline = getattr(part, "inline_data", None)
            if inline and inline.data:
                data = inline.data
                # Handle base64-encoded data
                if isinstance(data, str):
                    try:
                        decoded = base64.b64decode(data)
                    except Exception:
                        decoded = data.encode()
                else:
                    decoded = data
                
                mime_type = getattr(inline, "mime_type", "image/png")
                logger.info(f"Generated image: {len(decoded)} bytes, {mime_type}")
                return ImageResult(data=decoded, mime_type=mime_type)
        
        raise ImageGenError("No image data found in Gemini response")
        
    except ImageGenError:
        raise
    except Exception as exc:
        logger.exception("Gemini image generation failed")
        raise ImageGenError(f"Image generation failed: {exc}")


def generate_scope_image(
    solution_text: str,
    *,
    custom_prompt: Optional[str] = None,
    size: Optional[str] = None,
    api_key: Optional[str] = None,
) -> ImageResult:
    """
    Generate an image for a scope document's proposed solution.
    
    Args:
        solution_text: The proposed solution section content
        custom_prompt: Optional custom prompt template (use {solution_text} placeholder)
        size: Image size
        api_key: Optional API key override
    
    Returns:
        ImageResult with the generated image
    """
    prompt_template = custom_prompt or SCOPE_IMAGE_PROMPT
    prompt = prompt_template.format(solution_text=solution_text)
    return generate_image(prompt, size=size, api_key=api_key)


def generate_pso_image(
    solutions_text: str,
    *,
    custom_prompt: Optional[str] = None,
    size: Optional[str] = None,
    api_key: Optional[str] = None,
) -> ImageResult:
    """
    Generate a comparison matrix image for a PSO document.
    
    Args:
        solutions_text: The detailed solution breakdown content
        custom_prompt: Optional custom prompt template (use {solutions_text} placeholder)
        size: Image size
        api_key: Optional API key override
    
    Returns:
        ImageResult with the generated image
    """
    prompt_template = custom_prompt or PSO_IMAGE_PROMPT
    prompt = prompt_template.format(solutions_text=solutions_text)
    return generate_image(prompt, size=size, api_key=api_key)

