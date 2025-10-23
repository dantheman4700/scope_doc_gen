"""Scope Document Generator - AI-powered technical scope document automation."""

__version__ = "0.1.0"

from .ingest import DocumentIngester
from .llm import ClaudeExtractor
from .renderer import TemplateRenderer

__all__ = ['DocumentIngester', 'ClaudeExtractor', 'TemplateRenderer']

