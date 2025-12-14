"""Chat service for AI-powered document editing with Claude streaming."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Dict, List, Optional
from uuid import UUID

from anthropic import Anthropic

from server.core.config import (
    ANTHROPIC_API_KEY,
    CLAUDE_MODEL,
    WEB_SEARCH_MAX_USES,
    PERPLEXITY_API_KEY,
)
from server.core.research import PerplexityClient, ResearchFinding

logger = logging.getLogger(__name__)


@dataclass
class ChatMessage:
    """A message in the chat conversation."""
    role: str  # 'user' or 'assistant'
    content: str
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class EditSuggestion:
    """A suggested edit from the AI."""
    old_str: str
    new_str: str
    reason: Optional[str] = None


@dataclass
class SSEEvent:
    """Server-Sent Event for streaming responses."""
    event_type: str  # 'text', 'tool', 'error', 'done'
    data: Dict[str, Any]

    def to_sse(self) -> str:
        """Convert to SSE format string."""
        return f"event: {self.event_type}\ndata: {json.dumps(self.data)}\n\n"


# Tool definitions for Claude
DOCUMENT_TOOLS = [
    {
        "name": "str_replace_edit",
        "description": "Make a targeted edit to the document by replacing specific text. Use this for precise modifications without regenerating the entire document.",
        "input_schema": {
            "type": "object",
            "properties": {
                "old_str": {
                    "type": "string",
                    "description": "The exact text to replace. Must match exactly including whitespace.",
                },
                "new_str": {
                    "type": "string",
                    "description": "The new text to insert in place of old_str.",
                },
                "reason": {
                    "type": "string",
                    "description": "Brief explanation of why this change is being made.",
                },
            },
            "required": ["old_str", "new_str"],
        },
    },
    {
        "name": "highlight_ambiguity",
        "description": "Mark a section of the document as ambiguous or needing clarification.",
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "The ambiguous text to highlight.",
                },
                "concern": {
                    "type": "string",
                    "description": "Why this text is ambiguous and could cause issues.",
                },
                "suggestion": {
                    "type": "string",
                    "description": "Suggested clarification or rewrite.",
                },
            },
            "required": ["text", "concern"],
        },
    },
    {
        "name": "read_document",
        "description": "Read the current document content or a specific section.",
        "input_schema": {
            "type": "object",
            "properties": {
                "section": {
                    "type": "string",
                    "description": "Optional section heading to read. If not provided, returns entire document.",
                },
            },
        },
    },
    {
        "name": "create_version",
        "description": "Save the current state as a new version.",
        "input_schema": {
            "type": "object",
            "properties": {
                "description": {
                    "type": "string",
                    "description": "Description of the changes in this version.",
                },
            },
            "required": ["description"],
        },
    },
    {
        "name": "deep_research",
        "description": "Perform deep research using Perplexity AI for comprehensive information gathering. Use this for complex technical questions or when you need authoritative sources.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The research question or topic to investigate.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "calculate",
        "description": "Perform mathematical calculations to validate numbers, budgets, timelines, or other quantitative data in the document. Use this when you need to verify calculations or do math.",
        "input_schema": {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "A mathematical expression to evaluate (e.g., '100 * 1.5 + 50', '365 * 24', '(500000 * 0.15) / 12')",
                },
                "description": {
                    "type": "string",
                    "description": "What this calculation represents or why it's being done.",
                },
            },
            "required": ["expression"],
        },
    },
]


def safe_eval_math(expression: str) -> tuple[float | None, str | None]:
    """
    Safely evaluate a mathematical expression.
    Returns (result, error) tuple.
    """
    import ast
    import operator
    
    # Supported operators
    operators = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv,
        ast.Mod: operator.mod,
        ast.Pow: operator.pow,
        ast.USub: operator.neg,
        ast.UAdd: operator.pos,
    }
    
    def _eval(node):
        if isinstance(node, ast.Constant):  # Numbers
            return node.value
        elif isinstance(node, ast.BinOp):  # Binary operations
            left = _eval(node.left)
            right = _eval(node.right)
            op = operators.get(type(node.op))
            if op is None:
                raise ValueError(f"Unsupported operator: {type(node.op).__name__}")
            return op(left, right)
        elif isinstance(node, ast.UnaryOp):  # Unary operations
            operand = _eval(node.operand)
            op = operators.get(type(node.op))
            if op is None:
                raise ValueError(f"Unsupported operator: {type(node.op).__name__}")
            return op(operand)
        elif isinstance(node, ast.Expression):
            return _eval(node.body)
        else:
            raise ValueError(f"Unsupported expression type: {type(node).__name__}")
    
    try:
        # Parse the expression
        tree = ast.parse(expression, mode='eval')
        result = _eval(tree)
        return result, None
    except Exception as e:
        return None, str(e)


class DocumentChatService:
    """Service for AI-powered document chat and editing."""

    def __init__(self, api_key: str = None):
        """Initialize the chat service."""
        self.api_key = api_key or ANTHROPIC_API_KEY
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not configured")

        self.client = Anthropic(
            api_key=self.api_key,
            timeout=300.0,
        )
        self.model = CLAUDE_MODEL

    def _build_system_prompt(
        self,
        document_content: str,
        run_context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Build the system prompt for document chat."""
        context_info = ""
        if run_context:
            if run_context.get("project_name"):
                context_info += f"\nProject: {run_context['project_name']}"
            if run_context.get("template_type"):
                context_info += f"\nDocument Type: {run_context['template_type']}"

        return f"""You are an expert solutions architect and document editor working on a scope document.
{context_info}

CURRENT DOCUMENT:
{document_content}

YOUR CAPABILITIES:
1. Answer questions about the document content
2. Make targeted edits using str_replace_edit (preferred for small changes)
3. Identify and highlight ambiguous sections
4. Help improve clarity, completeness, and professionalism

EDITING GUIDELINES:
- Use str_replace_edit for targeted changes - never regenerate entire sections
- The old_str must match EXACTLY (including whitespace)
- Make one edit at a time for clarity
- Explain your changes briefly
- Preserve markdown formatting

When the user asks for changes:
1. First identify the exact text to change
2. Use str_replace_edit with the exact old text and new text
3. Provide a brief explanation

Be concise and helpful. Focus on improving the document quality."""

    async def stream_chat(
        self,
        message: str,
        document_content: str,
        conversation_history: List[ChatMessage],
        run_context: Optional[Dict[str, Any]] = None,
        enable_web_search: bool = False,
        use_perplexity: bool = False,
    ) -> AsyncIterator[SSEEvent]:
        """
        Stream a chat response with tool calls.
        
        Yields SSEEvent objects that can be serialized for the client.
        """
        system_prompt = self._build_system_prompt(document_content, run_context)

        # Build messages from conversation history
        messages = []
        for msg in conversation_history:
            messages.append({
                "role": msg.role,
                "content": msg.content,
            })

        # Add current message
        messages.append({
            "role": "user",
            "content": message,
        })

        # Build tools list
        tools = list(DOCUMENT_TOOLS)
        if enable_web_search:
            tools.append({
                "type": "web_search_20250305",
                "name": "web_search",
                "max_uses": WEB_SEARCH_MAX_USES,
            })

        try:
            # Use streaming for responses
            with self.client.messages.stream(
                model=self.model,
                max_tokens=8192,
                temperature=0.7,
                system=system_prompt,
                messages=messages,
                tools=tools,
            ) as stream:
                current_tool_use = None
                accumulated_text = ""

                for event in stream:
                    # Handle text deltas
                    if hasattr(event, 'type'):
                        if event.type == 'content_block_start':
                            block = getattr(event, 'content_block', None)
                            if block and getattr(block, 'type', None) == 'tool_use':
                                current_tool_use = {
                                    'id': getattr(block, 'id', ''),
                                    'name': getattr(block, 'name', ''),
                                    'input': '',
                                }

                        elif event.type == 'content_block_delta':
                            delta = getattr(event, 'delta', None)
                            if delta:
                                delta_type = getattr(delta, 'type', '')
                                
                                if delta_type == 'text_delta':
                                    text = getattr(delta, 'text', '')
                                    if text:
                                        accumulated_text += text
                                        yield SSEEvent(
                                            event_type='text',
                                            data={'content': text}
                                        )
                                
                                elif delta_type == 'input_json_delta':
                                    partial_json = getattr(delta, 'partial_json', '')
                                    if current_tool_use and partial_json:
                                        current_tool_use['input'] += partial_json

                        elif event.type == 'content_block_stop':
                            if current_tool_use:
                                # Parse the accumulated JSON input
                                try:
                                    tool_input = json.loads(current_tool_use['input'])
                                except json.JSONDecodeError:
                                    tool_input = {}

                                yield SSEEvent(
                                    event_type='tool',
                                    data={
                                        'id': current_tool_use['id'],
                                        'name': current_tool_use['name'],
                                        'input': tool_input,
                                    }
                                )
                                current_tool_use = None

                        elif event.type == 'message_stop':
                            yield SSEEvent(
                                event_type='done',
                                data={'total_text': accumulated_text}
                            )

        except Exception as exc:
            logger.exception(f"Chat streaming failed: {exc}")
            yield SSEEvent(
                event_type='error',
                data={'message': str(exc)}
            )

    def apply_edit(
        self,
        document: str,
        old_str: str,
        new_str: str,
    ) -> tuple[str, bool]:
        """
        Apply a str_replace edit to a document.
        
        Returns (new_document, success).
        """
        if old_str not in document:
            logger.warning(f"Edit failed: old_str not found in document")
            return document, False

        # Count occurrences
        count = document.count(old_str)
        if count > 1:
            logger.warning(f"Edit warning: old_str found {count} times, replacing first occurrence")

        new_document = document.replace(old_str, new_str, 1)
        return new_document, True

    def deep_research(self, query: str) -> Optional[ResearchFinding]:
        """
        Perform deep research using Perplexity AI.
        
        Returns ResearchFinding or None if Perplexity is not configured.
        """
        if not PERPLEXITY_API_KEY:
            logger.warning("Perplexity API key not configured for deep research")
            return None

        try:
            client = PerplexityClient(PERPLEXITY_API_KEY)
            return client.query(query)
        except Exception as exc:
            logger.exception(f"Deep research failed: {exc}")
            return None


# Singleton instance
_chat_service: Optional[DocumentChatService] = None


def get_chat_service() -> DocumentChatService:
    """Get or create the chat service singleton."""
    global _chat_service
    if _chat_service is None:
        _chat_service = DocumentChatService()
    return _chat_service
