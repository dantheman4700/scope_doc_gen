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
        Stream a chat response with tool calls and agentic loop.
        
        Yields SSEEvent objects that can be serialized for the client.
        When Claude makes tool calls, this executes them and continues.
        """
        system_prompt = self._build_system_prompt(document_content, run_context)

        # Build messages from conversation history - filter empty content
        messages = []
        for msg in conversation_history:
            if msg.content and msg.content.strip():
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

        # Agentic loop - continue until no more tool calls
        max_iterations = 10  # Safety limit
        iteration = 0
        
        while iteration < max_iterations:
            iteration += 1
            
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
                    tool_calls_in_response = []
                    stop_reason = None

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

                                    tool_call = {
                                        'id': current_tool_use['id'],
                                        'name': current_tool_use['name'],
                                        'input': tool_input,
                                    }
                                    tool_calls_in_response.append(tool_call)
                                    
                                    # Yield tool event to frontend
                                    yield SSEEvent(
                                        event_type='tool',
                                        data=tool_call
                                    )
                                    current_tool_use = None

                            elif event.type == 'message_stop':
                                stop_reason = "end_turn"
                                
                            elif event.type == 'message_delta':
                                delta = getattr(event, 'delta', None)
                                if delta:
                                    stop_reason = getattr(delta, 'stop_reason', stop_reason)

                    # After stream ends, check if we need to continue with tool results
                    if not tool_calls_in_response:
                        # No tool calls - we're done
                        yield SSEEvent(
                            event_type='done',
                            data={'total_text': accumulated_text}
                        )
                        return
                    
                    # Execute tools and build tool results
                    tool_results = []
                    for tool_call in tool_calls_in_response:
                        tool_name = tool_call['name']
                        tool_input = tool_call['input']
                        tool_id = tool_call['id']
                        
                        result_content = self._execute_tool(
                            tool_name, tool_input, document_content
                        )
                        
                        # Yield tool result event
                        yield SSEEvent(
                            event_type='tool_result',
                            data={
                                'id': tool_id,
                                'name': tool_name,
                                'result': result_content[:500] if len(result_content) > 500 else result_content,
                            }
                        )
                        
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_id,
                            "content": result_content,
                        })
                    
                    # Build assistant message with tool uses
                    assistant_content = []
                    if accumulated_text:
                        assistant_content.append({
                            "type": "text",
                            "text": accumulated_text,
                        })
                    for tool_call in tool_calls_in_response:
                        assistant_content.append({
                            "type": "tool_use",
                            "id": tool_call['id'],
                            "name": tool_call['name'],
                            "input": tool_call['input'],
                        })
                    
                    # Add assistant response and tool results to messages for next iteration
                    messages.append({
                        "role": "assistant",
                        "content": assistant_content,
                    })
                    messages.append({
                        "role": "user",
                        "content": tool_results,
                    })

            except Exception as exc:
                logger.exception(f"Chat streaming failed: {exc}")
                yield SSEEvent(
                    event_type='error',
                    data={'message': str(exc)}
                )
                return
        
        # Max iterations reached
        yield SSEEvent(
            event_type='done',
            data={'total_text': 'Reached maximum tool iterations'}
        )

    def _execute_tool(
        self,
        tool_name: str,
        tool_input: Dict[str, Any],
        document_content: str,
    ) -> str:
        """Execute a tool and return the result as a string."""
        
        if tool_name == "read_document":
            section = tool_input.get("section")
            if section:
                # Try to find the section in the document
                lines = document_content.split('\n')
                in_section = False
                section_content = []
                for line in lines:
                    if line.startswith('#') and section.lower() in line.lower():
                        in_section = True
                    elif in_section and line.startswith('#'):
                        break
                    elif in_section:
                        section_content.append(line)
                if section_content:
                    return '\n'.join(section_content)
                return f"Section '{section}' not found. Full document:\n{document_content[:2000]}"
            return document_content
        
        elif tool_name == "calculate":
            expression = tool_input.get("expression", "")
            description = tool_input.get("description", "")
            result, error = safe_eval_math(expression)
            if error:
                return f"Calculation error: {error}"
            return f"Result of {expression} = {result}" + (f" ({description})" if description else "")
        
        elif tool_name == "deep_research":
            query = tool_input.get("query", "")
            if not PERPLEXITY_API_KEY:
                return "Deep research is not available (Perplexity API key not configured)"
            try:
                client = PerplexityClient(PERPLEXITY_API_KEY)
                finding = client.query(query)
                if finding:
                    result = f"Research findings for: {query}\n\n{finding.content}"
                    if finding.sources:
                        result += "\n\nSources:\n" + "\n".join(f"- {s}" for s in finding.sources[:5])
                    return result
                return f"No research results found for: {query}"
            except Exception as exc:
                logger.exception(f"Deep research failed: {exc}")
                return f"Research failed: {str(exc)}"
        
        elif tool_name == "str_replace_edit":
            # str_replace_edit is handled by the frontend, just acknowledge
            return "Edit suggestion recorded. The user will review and apply this change."
        
        elif tool_name == "highlight_ambiguity":
            # highlight_ambiguity is handled by the frontend
            return "Ambiguity highlighted. The user can see this in the document."
        
        elif tool_name == "create_version":
            # create_version would need backend integration
            return "Version creation noted. Use the Save button to create a new version."
        
        else:
            return f"Unknown tool: {tool_name}"

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
