"""LLM interaction module for variable extraction using Claude."""
from __future__ import annotations

import json
import logging
import time
import sys
import base64
from typing import Dict, Any, List, Tuple, Optional
from anthropic import Anthropic
from .config import (
    ANTHROPIC_API_KEY,
    CLAUDE_MODEL,
    CLAUDE_THINKING_BUDGET,
    MAX_TOKENS,
    TEMPERATURE,
    ENABLE_WEB_RESEARCH,
    WEB_SEARCH_MAX_USES,
    WEB_SEARCH_ALLOWED_DOMAINS,
)

logger = logging.getLogger(__name__)


class ClaudeExtractor:
    """Handles interaction with Claude API for variable extraction."""
    
    def __init__(self, api_key: str = None):
        """Initialize Claude client."""
        self.api_key = api_key or ANTHROPIC_API_KEY
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not found. Please set it in .env file")
        
        # Add timeout to prevent hanging - 5 minutes for large requests
        self.client = Anthropic(
            api_key=self.api_key,
            timeout=300.0,  # 5 minutes timeout
        )
        self.model = CLAUDE_MODEL
        self.tools: List[Dict[str, Any]] = []
        if ENABLE_WEB_RESEARCH:
            tool: Dict[str, Any] = {
                "type": "web_search_20250305",
                "name": "web_search",
                "max_uses": WEB_SEARCH_MAX_USES,
            }
            if WEB_SEARCH_ALLOWED_DOMAINS:
                tool["allowed_domains"] = WEB_SEARCH_ALLOWED_DOMAINS
            self.tools.append(tool)
    
    @property
    def supports_web_search(self) -> bool:
        return bool(self.tools)

    def extract_variables(
        self,
        combined_documents: str,
        variables_schema: Dict[str, Any],
        variables_guide: Dict[str, Any],
        file_context: Optional[Dict[str, str]] = None,
        attachments: Optional[List[Dict[str, Any]]] = None,
        use_web_search: bool = False,
    ) -> Dict[str, Any]:
        """
        Extract all variables from documents using Claude.
        
        Args:
            combined_documents: Combined text from all input documents
            variables_schema: JSON schema defining variable structure
            variables_guide: Detailed guide for each variable with style info
            
        Returns:
            Dictionary of extracted variables
        """
        print("\n[INFO] Analyzing documents with Claude...")
        
        # Build the system prompt
        system_prompt = self._build_system_prompt(variables_schema, variables_guide)
        
        # Build the user message
        message_content = self._build_message_content(
            combined_documents,
            file_context,
            attachments,
            include_debug_note=False,
        )
        
        attempt = 0
        while True:
            try:
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=MAX_TOKENS,
                    temperature=1,  # Must be 1 when thinking is enabled
                    thinking={"type": "enabled", "budget_tokens": CLAUDE_THINKING_BUDGET},
                    system=system_prompt,
                    messages=[
                        {"role": "user", "content": message_content}
                    ],
                    tools=self.tools if (use_web_search and self.tools) else None,
                )
                
                # Check for web search tool usage and print results
                self._print_web_search_usage(response)
                
                # Extract text from response - handle multiple content blocks
                response_text = self._extract_text_from_response(response)
                if not response_text:
                    raise ValueError("No text content found in Claude response")
                
                variables = self._parse_response(response_text)
                print("[OK] Variable extraction complete")
                return variables
            except Exception as e:
                # Log the actual response for debugging
                if 'response_text' in locals():
                    print(f"[DEBUG] Claude response (first 500 chars): {response_text[:500]}")
                    print(f"[DEBUG] Response length: {len(response_text)} chars")
                enc = sys.stdout.encoding or 'utf-8'
                msg = str(e).encode(enc, errors='ignore').decode(enc)
                if 'rate_limit' in msg or '429' in msg:
                    wait = [30, 60, 120][attempt] if attempt < 3 else 120
                    print(f"[WARN] Rate limit on extraction. Retrying in {wait}s (attempt {attempt+1})")
                    time.sleep(wait)
                    attempt += 1
                    if attempt >= 3:
                        print("[ERROR] Extraction failed after retries")
                        raise
                    continue
                print(f"[ERROR] Claude API call failed: {msg}")
                raise

    def rewrite_variables(
        self,
        current_variables: Dict[str, Any],
        change_instructions: str,
        variables_schema: Dict[str, Any],
        variables_guide: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Apply high-level change instructions to an existing variables JSON payload."""

        if not change_instructions.strip():
            return current_variables

        system_prompt = (
            "You are an expert solutions architect updating a scope document JSON payload. "
            "You will be given the current variables JSON along with change instructions. "
            "Apply the changes, preserve unspecified fields, and ensure the result matches the schema and style guide.\n\n"
            f"VARIABLES SCHEMA:\n{json.dumps(variables_schema, indent=2)}\n\n"
            f"VARIABLES STYLE GUIDE:\n{json.dumps(variables_guide, indent=2)}\n\n"
            "Return ONLY the full updated JSON object."
        )

        user_prompt = (
            "CURRENT VARIABLES JSON:\n"
            f"{json.dumps(current_variables, indent=2)}\n\n"
            "CHANGE INSTRUCTIONS:\n"
            f"{change_instructions}\n\n"
            "Update the JSON to reflect the requested changes. Do not remove fields unless explicitly instructed."
        )

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=MAX_TOKENS,
                temperature=1,  # Must be 1 when thinking is enabled
                thinking={"type": "enabled", "budget_tokens": CLAUDE_THINKING_BUDGET},
                system=system_prompt,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": user_prompt,
                            }
                        ],
                    }
                ],
            )
        except Exception as exc:
            print(f"[ERROR] Failed to update variables: {exc}")
            return current_variables

        response_text = self._extract_text_from_response(response)
        if not response_text:
            print("[WARN] No text content in response; returning original values")
            return current_variables
        try:
            return self._parse_response(response_text)
        except Exception:
            print("[WARN] Could not parse updated variables; returning original values")
            return current_variables

    def generate_oneshot_markdown(
        self,
        *,
        combined_documents: str,
        template_text: str,
        instructions: Optional[str] = None,
        solution_hint: Optional[str] = None,
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Generate raw markdown directly (no variable extraction) and capture feedback.
        Returns (markdown, feedback_dict).
        """
        system_prompt = (
            "You are producing a scope document in markdown that must strictly follow the provided template structure. "
            "Do not change headings or ordering. Keep the content concise and complete. "
            "Return a JSON object with keys: "
            '"markdown" (full rendered markdown string) and '
            '"feedback" with keys uncertain_areas, low_confidence_sections, missing_information, notes. '
            "Keep feedback concise and actionable. "
            "IMPORTANT: Here are transcripts and example files and other supporting information. "
            "Here is the scope template to follow. We are creating this job in the specified solution type. "
            "Change nothing about the scope structure or organization, follow it to a T, and create the scope based on our inputs and desired solution type. "
            "CRITICAL: When generating markdown tables, preserve the exact table structure from the template. "
            "Tables must use proper markdown table format with pipe separators (|) and alignment markers (| :---- |) in the separator row. "
            "Do not convert tables to plain text or lists - maintain them as markdown tables."
        )

        # Build user content with the specific oneshot prompt format
        user_parts = [
            "Here are transcripts and example files and other supporting information.",
            "Here is the scope template to follow.",
        ]
        if solution_hint:
            user_parts.append(f"We are creating this job in {solution_hint}.")
        else:
            user_parts.append("We are creating this job in the specified solution type.")
        
        user_parts.extend([
            "Change nothing about the scope structure or organization, follow it to a T, and create the scope based on our inputs and desired solution type.",
            "",
            "SCOPE TEMPLATE:",
            template_text,
            "",
            "INPUT DOCUMENTS (combined):",
            combined_documents,
        ])
        
        if instructions:
            user_parts.extend([
                "",
                "ADDITIONAL INSTRUCTIONS:",
                instructions,
            ])

        user_blocks: List[Dict[str, Any]] = [
            {"type": "text", "text": "\n".join(user_parts)}
        ]

        # Use structured outputs (beta) to force JSON shape with extended thinking
        logger.info(f"Calling Claude API for oneshot generation (model={self.model}, timeout=300s, thinking_budget={CLAUDE_THINKING_BUDGET})")
        try:
            response = self.client.beta.messages.create(
                model=self.model,
                max_tokens=MAX_TOKENS,
                temperature=1,  # Must be 1 when thinking is enabled
                thinking={"type": "enabled", "budget_tokens": CLAUDE_THINKING_BUDGET},
                system=system_prompt,
                messages=[
                    {
                        "role": "user",
                        "content": user_blocks,
                    }
                ],
                betas=["structured-outputs-2025-11-13"],
                output_format={
                    "type": "json_schema",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "markdown": {"type": "string"},
                            "feedback": {
                                "type": "object",
                                "properties": {
                                    "uncertain_areas": {"type": "array", "items": {"type": "string"}},
                                    "low_confidence_sections": {"type": "array", "items": {"type": "string"}},
                                    "missing_information": {"type": "array", "items": {"type": "string"}},
                                    "notes": {"type": "string"},
                                },
                                "required": [
                                    "uncertain_areas",
                                    "low_confidence_sections",
                                    "missing_information",
                                ],
                                "additionalProperties": False,
                            },
                        },
                        "required": ["markdown", "feedback"],
                        "additionalProperties": False,
                    },
                },
            )
            logger.info("Claude API call completed successfully")
        except Exception as api_exc:
            logger.exception(f"Claude API call failed: {api_exc}")
            raise

        # Check for refusal or max_tokens - structured outputs may not match schema in these cases
        stop_reason = getattr(response, 'stop_reason', None)
        logger.info(f"Claude response stop_reason: {stop_reason}")
        
        if stop_reason == "refusal":
            logger.warning("Claude refused the request - output may not match schema")
            raise ValueError("Claude refused to generate the scope document. This may be due to safety filters or content policy.")
        elif stop_reason == "max_tokens":
            logger.warning("Response hit max_tokens limit - output may be incomplete or invalid")
            raise ValueError(f"Response was cut off due to token limit ({MAX_TOKENS} tokens). The generated content may be incomplete. Try increasing MAX_TOKENS or reducing input size.")

        # Extract text from response - with thinking enabled, need to find text blocks
        response_text = ""
        try:
            if not hasattr(response, 'content') or not response.content:
                raise ValueError("Claude response has no content blocks")
            
            # Search for text blocks (skip thinking blocks)
            for block in response.content:
                if hasattr(block, "type") and block.type == "text":
                    if hasattr(block, "text") and block.text:
                        response_text = block.text
                        break
                elif hasattr(block, "text") and block.text:
                    # Fallback for blocks without explicit type
                    response_text = block.text
                    break
            
            logger.info(f"Extracted response text, length: {len(response_text)}")
            if response_text:
                # Log first 200 chars for debugging
                preview = response_text[:200] if len(response_text) > 200 else response_text
                logger.debug(f"Response preview: {preview}...")
        except Exception as parse_exc:
            logger.exception(f"Failed to extract response text: {parse_exc}")
            # Try to get raw response for debugging
            logger.error(f"Response object type: {type(response)}, attributes: {dir(response)}")
            response_text = ""

        if not response_text:
            raise ValueError("Claude response was empty or could not be parsed")
            
        markdown, feedback = self._parse_oneshot_response(response_text)
        if not markdown:
            raise ValueError("Claude response did not include markdown content")
        logger.info(f"Successfully parsed oneshot response, markdown length: {len(markdown)}")
        return markdown, feedback

    def generate_feedback(
        self,
        *,
        combined_documents: str,
        variables: Optional[Dict[str, Any]] = None,
        output_markdown: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Ask the model for a concise feedback/confidence report.
        """
        system_prompt = (
            "Provide a concise feedback/confidence report for the scope. "
            "Return ONLY JSON with keys: uncertain_areas (list), low_confidence_sections (list), "
            "missing_information (list), notes (string). Keep lists short and actionable."
        )

        parts: List[str] = []
        if variables is not None:
            try:
                parts.append("EXTRACTED VARIABLES:\n" + json.dumps(variables, indent=2))
            except Exception:
                pass
        if output_markdown:
            parts.append("RENDERED MARKDOWN (if available):\n" + output_markdown)
        # Provide a compact slice of documents to ground feedback
        preview = combined_documents[:6000]
        parts.append("DOCUMENT CONTEXT (first 6000 chars):\n" + preview)

        user_prompt = "\n\n".join(parts)

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=16000,  # Must be > thinking.budget_tokens (12000)
                temperature=1,  # Must be 1 when thinking is enabled
                thinking={"type": "enabled", "budget_tokens": CLAUDE_THINKING_BUDGET},
                system=system_prompt,
                messages=[
                    {
                        "role": "user",
                        "content": [{"type": "text", "text": user_prompt}],
                    }
                ],
            )
            text = self._extract_text_from_response(response)
            return self._parse_feedback_json(text)
        except Exception as exc:
            logger.exception(f"Feedback generation failed: {exc}")
            return {}

    def generate_questions(
        self,
        *,
        scope_markdown: str,
    ) -> Dict[str, List[str]]:
        """
        Generate clarifying questions based on the scope document.
        
        Returns a dict with:
        - questions_for_expert: Technical clarifications for solutions architect
        - questions_for_client: Follow-up questions to ask the client
        """
        system_prompt = (
            "You are a senior solutions architect reviewing a scope document. "
            "Generate two sets of questions:\n"
            "1. 'questions_for_expert': Technical clarifications that a solutions architect "
            "should answer before implementation (e.g., architecture decisions, integration details, "
            "technical feasibility concerns).\n"
            "2. 'questions_for_client': Follow-up questions that should be asked to the client "
            "to fill in gaps or clarify requirements (e.g., business priorities, edge cases, "
            "preferences, constraints).\n\n"
            "IMPORTANT: Generate as many or as few questions as genuinely needed. Only include questions "
            "you are confident would materially improve the scope. If the scope is comprehensive and clear, "
            "it's okay to have fewer questions. If there are many gaps, include more. Quality over quantity.\n\n"
            "Return ONLY valid JSON with these two keys, each containing a list of questions. "
            "Each question should be specific, actionable, and add real value."
        )

        user_prompt = f"SCOPE DOCUMENT:\n\n{scope_markdown}\n\nGenerate clarifying questions for this scope."

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=16000,  # Must be > thinking.budget_tokens (12000)
                temperature=1,  # Must be 1 when thinking is enabled
                thinking={"type": "enabled", "budget_tokens": CLAUDE_THINKING_BUDGET},
                system=system_prompt,
                messages=[
                    {
                        "role": "user",
                        "content": [{"type": "text", "text": user_prompt}],
                    }
                ],
            )
            text = self._extract_text_from_response(response)
            logger.info(f"Questions raw response text (first 500 chars): {text[:500] if text else 'EMPTY'}")
            result = self._parse_feedback_json(text)
            logger.info(f"Parsed questions result: {result}")
            # Ensure required keys exist
            return {
                "questions_for_expert": result.get("questions_for_expert", []),
                "questions_for_client": result.get("questions_for_client", []),
            }
        except Exception as exc:
            logger.exception(f"Question generation failed: {exc}")
            return {"questions_for_expert": [], "questions_for_client": []}

    def extract_variables_with_raw(
        self,
        combined_documents: str,
        variables_schema: Dict[str, Any],
        variables_guide: Dict[str, Any],
        file_context: Optional[Dict[str, str]] = None,
        attachments: Optional[List[Dict[str, Any]]] = None,
        use_web_search: bool = False,
    ) -> Tuple[Dict[str, Any], str]:
        """
        Same as extract_variables, but also returns the raw model text for debugging.
        Tries to enforce JSON-only output via response_format when available.
        """
        print("\n[INFO] Analyzing documents with Claude (debug mode)...")

        system_prompt = self._build_system_prompt(variables_schema, variables_guide)
        message_content = self._build_message_content(
            combined_documents,
            file_context,
            attachments,
            include_debug_note=True,
        )

        attempt = 0
        while True:
            try:
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=MAX_TOKENS,
                    temperature=1,  # Must be 1 when thinking is enabled
                    thinking={"type": "enabled", "budget_tokens": CLAUDE_THINKING_BUDGET},
                    system=system_prompt,
                    messages=[
                        {"role": "user", "content": message_content}
                    ],
                    tools=self.tools if (use_web_search and self.tools) else None,
                )
                
                # Check for web search tool usage and print results
                self._print_web_search_usage(response)
                
                # Extract text from response - handle multiple content blocks
                response_text = self._extract_text_from_response(response)
                if not response_text:
                    raise ValueError("No text content found in Claude response")
                
                variables = self._parse_response(response_text)
                print("[OK] Variable extraction complete")
                return variables, response_text
            except Exception as e:
                enc = sys.stdout.encoding or 'utf-8'
                msg = str(e).encode(enc, errors='ignore').decode(enc)
                if 'rate_limit' in msg or '429' in msg:
                    wait = [30, 60, 120][attempt] if attempt < 3 else 120
                    print(f"[WARN] Rate limit on extraction. Retrying in {wait}s (attempt {attempt+1})")
                    time.sleep(wait)
                    attempt += 1
                    if attempt >= 3:
                        print("[ERROR] Extraction failed after retries")
                        raise
                    continue
                print(f"[ERROR] Claude API call failed: {msg}")
                raise
    
    def refine_variable(
        self,
        variable_name: str,
        current_value: Any,
        context: str,
        variable_guide: Dict[str, Any]
    ) -> Any:
        """
        Refine a specific variable with additional context or corrections.
        
        Args:
            variable_name: Name of the variable to refine
            current_value: Current value of the variable
            context: Additional context or instructions
            variable_guide: Guide for the variable
            
        Returns:
            Refined variable value
        """
        print(f"\n[INFO] Refining variable: {variable_name}")
        
        # Find variable definition
        var_def = next(
            (v for v in variable_guide.get('variables', []) if v['name'] == variable_name),
            None
        )
        
        if not var_def:
            print(f"[WARN] Variable {variable_name} not found in guide")
            return current_value
        
        prompt = f"""You are refining a specific variable for a technical scope document.

Variable: {variable_name}
Description: {var_def.get('description', '')}
Style: {var_def.get('style', '')}
Current Value: {json.dumps(current_value, indent=2)}

Additional Context/Instructions:
{context}

Please provide the refined value for this variable. Return ONLY the value in the appropriate format (JSON array if it's a list, plain text otherwise). Do not include explanations."""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4000,
                temperature=1,  # Must be 1 when thinking is enabled
                thinking={"type": "enabled", "budget_tokens": CLAUDE_THINKING_BUDGET},
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            
            response_text = self._extract_text_from_response(response).strip()
            if not response_text:
                print("[WARN] No text content in refinement response")
                return current_value
            
            # Try to parse as JSON if it looks like JSON
            if response_text.startswith('[') or response_text.startswith('{'):
                try:
                    return json.loads(response_text)
                except json.JSONDecodeError:
                    pass
            
            return response_text
            
        except Exception as e:
            print(f"[ERROR] Error refining variable: {str(e)}")
            return current_value
    
    def _build_system_prompt(
        self,
        variables_schema: Dict[str, Any],
        variables_guide: Dict[str, Any]
    ) -> str:
        """Build the system prompt for Claude."""
        return f"""You are an expert at analyzing business documents and extracting structured information for technical scope documents.

Your task is to analyze the provided documents and extract variables according to the schema and style guide below.

VARIABLES SCHEMA:
{json.dumps(variables_schema, indent=2)}

VARIABLES STYLE GUIDE:
{json.dumps(variables_guide, indent=2)}

INSTRUCTIONS:
1. Carefully read all provided documents
2. Extract information for each variable defined in the schema
3. Follow the style guidelines for content and tone, but DO NOT include markdown formatting syntax (like **bold** or *italic*) in your JSON values
4. Return plain text values - the template will handle all markdown formatting
5. For array variables, return simple string values without markdown prefixes (no '* ' bullets)
6. If information is not available in the documents, make reasonable inferences based on context or use "TBD" for missing critical information
7. Ensure all required fields have values
8. Prefer brevity and skimmability. When a style says "top N" or "2–4 lines", adhere strictly.
9. Respect array size limits specified in the JSON schema (e.g., maxItems). Do not exceed these limits; if you have more candidates, select the most important and drop the rest.
9. When listing services/tech stack/integration points, ONLY include services with publicly documented APIs or automation methods. If uncertain, USE the web_search tool to verify official documentation. If still uncertain after searching, mark the item as "TBD – verify availability" and avoid inventing APIs (e.g., do not claim an "iCloud API"; prefer the correct product name like "Apple CloudKit REST" if verified).
10. Risks: limit to 3–5 bullets; generalize repeated themes (e.g., combine API rate limits into a single generic risk). Do NOT include provider-specific rate numbers.
11. Timeline & Milestones: provide one line per phase in the form "Phase – short description: X weeks (Y hr)". Include an hours allocation Y for each phase such that the SUM across all phases equals the total hours from dev_hours + training_hours + pm_hours. You may place most/all training and PM hours in the final phase. Use the unit 'hr' in parentheses and do NOT write this section as a paragraph.
12. Setup Costs (dev/training/PM hours): provide totals only in the form "X hours". No parentheses or breakdowns; details live in Timeline & Milestones.
13. Subscription/Licensing: avoid outdated model names like "gpt-4". Prefer current product names or generic phrasing like "AI API usage".
14. Return the results as a valid JSON object

JSON FORMATTING REQUIREMENTS:
- All string values must have properly escaped quotes and newlines
- Use \\n for newlines within strings, not literal newlines
- Ensure all strings are properly terminated with closing quotes
- Validate that all brackets and braces are properly closed
- Do not truncate the JSON - ensure it is complete and valid

ASSUMPTIONS:
1. The development labor rate is fixed at $200/hour. When interpreting or calculating development-related costs, use $200/hr unless explicit, contradictory pricing is stated in the documents.

Your response should be ONLY a valid, complete JSON object with the extracted variables. Do not include any explanations or additional text before or after the JSON."""
    
    def _build_message_content(
        self,
        combined_documents: str,
        file_context: Optional[Dict[str, str]] = None,
        attachments: Optional[List[Dict[str, Any]]] = None,
        include_debug_note: bool = False,
    ) -> List[Dict[str, Any]]:
        blocks: List[Dict[str, Any]] = []

        if attachments:
            for attachment in attachments:
                blocks.append(attachment)

        context_section = ""
        if file_context:
            lines = ["FILE CONTEXT (per source document):"]
            for fname, note in file_context.items():
                lines.append(f"- {fname}: {note}")
            context_section = "\n" + "\n".join(lines) + "\n"

        # Build prompt - note that binary files (PDFs, images) are attached separately
        prompt_parts = []
        if context_section:
            prompt_parts.append(context_section)
        
        if attachments:
            prompt_parts.append(
                f"\n{len(attachments)} document(s)/image(s) are attached above as native files for your analysis."
            )
        
        if combined_documents and combined_documents.strip():
            prompt_parts.append("\nAdditional context and text documents:\n\n")
            prompt_parts.append(combined_documents)
        
        prompt_parts.append(
            "\n\nPlease extract all variables from the provided documents (both attached files and text content) according to the schema and style guide provided in the system prompt."
        )
        
        prompt = "".join(prompt_parts)

        if include_debug_note:
            prompt += "\n\nReturn ONLY a valid JSON object with no extra text."

        blocks.append({"type": "text", "text": prompt})
        return blocks

    # ---------- Project Filtering ----------
    def filter_for_project(
        self,
        combined_documents: str,
        project_identifier: str,
        file_context: Dict[str, str] | None = None
    ) -> str:
        """
        Use Claude to isolate content relevant to a single project from mixed documents.

        Args:
            combined_documents: The full combined documents text
            project_identifier: A string to identify the target project. This can include
                                project name, client, keywords, or constraints (e.g.,
                                "Client: Acme Corp; Project: Contract Automation").

        Returns:
            A filtered text block containing only project-relevant excerpts, with
            provenance markers per excerpt.
        """
        system = (
            "You are a document triage assistant. Extract only the passages relevant to the "
            "target project. Preserve original wording. Include brief provenance headers "
            "like '[[FILENAME | page/line approx]]' when possible based on separators."
        )

        context_section = ""
        if file_context:
            lines = ["FILE CONTEXT (per source document):"]
            for fname, note in file_context.items():
                lines.append(f"- {fname}: {note}")
            context_section = "\n" + "\n".join(lines) + "\n"

        user = f"""TARGET PROJECT IDENTIFIER:
{project_identifier}

{context_section}
DOCUMENTS:
{combined_documents}

INSTRUCTIONS:
1) Return ONLY relevant excerpts for the target project, preserving exact phrasing.
2) Group excerpts by source document using the DOCUMENT separators present.
3) If a section is ambiguous, include it but mark with '[AMBIGUOUS]'.
4) If nothing matches, return an empty string.
"""

        # Chunk large inputs to avoid rate limits; try to keep chunks modest
        chunks = self._chunk_documents(combined_documents, max_chars=120_000)
        print(f"[INFO] Filtering across {len(chunks)} chunk(s)")

        filtered_parts: List[str] = []
        for idx, chunk in enumerate(chunks, start=1):
            print(f"[INFO] Filtering chunk {idx}/{len(chunks)} (len={len(chunk)})")

            user_chunk = f"""TARGET PROJECT IDENTIFIER:
{project_identifier}

DOCUMENTS (CHUNK {idx}/{len(chunks)}):
{chunk}

INSTRUCTIONS:
1) Return ONLY relevant excerpts for the target project, preserving exact phrasing.
2) Group excerpts by source document using the DOCUMENT separators present.
3) If a section is ambiguous, include it but mark with '[AMBIGUOUS]'.
4) If nothing matches, return an empty string.
"""

            # Exponential backoff for rate limits
            attempt = 0
            while True:
                try:
                    response = self.client.messages.create(
                        model=self.model,
                        max_tokens=min(3000, MAX_TOKENS),
                        temperature=1,  # Must be 1 when thinking is enabled
                        thinking={"type": "enabled", "budget_tokens": CLAUDE_THINKING_BUDGET},
                        system=system,
                        messages=[{"role": "user", "content": user_chunk}],
                    )
                    part = self._extract_text_from_response(response).strip()
                    if part:
                        filtered_parts.append(part)
                    break
                except Exception as e:
                    enc = sys.stdout.encoding or 'utf-8'
                    msg = str(e).encode(enc, errors='ignore').decode(enc)
                    if 'rate_limit' in msg or '429' in msg:
                        wait = min(20, 5 * (2 ** attempt))
                        print(f"[WARN] Rate limit on chunk {idx}. Retrying in {wait}s (attempt {attempt+1})")
                        time.sleep(wait)
                        attempt += 1
                        if attempt >= 3:
                            print("[ERROR] Too many rate limit retries; skipping remaining chunks")
                            return "\n\n".join(filtered_parts).strip()
                        continue
                    else:
                        print(f"[ERROR] Filter call failed on chunk {idx}: {e}")
                        break

        return "\n\n".join(filtered_parts).strip()

    def _chunk_documents(self, text: str, max_chars: int = 120_000) -> List[str]:
        """Chunk the combined documents text, keeping document boundaries when possible."""
        sep = "\n\n" + ("=" * 80) + "\n"
        parts = text.split(sep)
        chunks: List[str] = []
        current: List[str] = []
        current_len = 0

        for i, part in enumerate(parts):
            # Re-add separator except before the first part
            add = (sep if current else "") + part if current else part
            if current_len + len(add) > max_chars and current:
                chunks.append("".join(current))
                current = [part]
                current_len = len(part)
            else:
                current.append(add)
                current_len += len(add)

        if current:
            chunks.append("".join(current))

        # Fallback if separator not found
        if len(chunks) == 1 and len(chunks[0]) > max_chars:
            raw = chunks[0]
            chunks = [raw[i:i + max_chars] for i in range(0, len(raw), max_chars)]

        return chunks
    
    def _print_web_search_usage(self, response: Any) -> None:
        """Print web search results if the model used the web_search tool."""
        if not hasattr(response, 'content'):
            return
        
        search_count = 0
        for block in response.content:
            if hasattr(block, 'type') and block.type == 'tool_use':
                if hasattr(block, 'name') and block.name == 'web_search':
                    search_count += 1
                    # Print the search query if available
                    if hasattr(block, 'input') and isinstance(block.input, dict):
                        query = block.input.get('query', 'N/A')
                        print(f"\n[WEB SEARCH #{search_count}] Query: {query}")
            
            # Look for tool results in the response
            if hasattr(block, 'type') and block.type == 'tool_result':
                if hasattr(block, 'content'):
                    try:
                        # Claude returns web search results as structured data
                        # Try to extract URLs from the result
                        result_text = str(block.content)
                        # Parse for URLs if available in the result
                        import re
                        urls = re.findall(r'https?://[^\s<>"{}|\\^`\[\]]+', result_text)
                        if urls:
                            print(f"[WEB SEARCH] Found {len(urls)} source(s):")
                            for url in urls[:5]:  # Limit to first 5 to avoid spam
                                print(f"  → {url}")
                    except Exception:
                        pass  # Silently skip if parsing fails
    
    def _extract_text_from_response(self, response: Any) -> str:
        """Extract text content from Claude response, handling multiple content blocks."""
        if not hasattr(response, 'content'):
            return ""
        
        # Collect all text blocks from the response
        text_parts = []
        for block in response.content:
            if hasattr(block, 'type') and block.type == 'text':
                if hasattr(block, 'text'):
                    text_parts.append(block.text)
        
        return "\n".join(text_parts)
    
    def _parse_oneshot_response(self, response_text: str) -> Tuple[str, Dict[str, Any]]:
        """Parse oneshot JSON payload into (markdown, feedback)."""
        text = response_text.strip()
        
        # Log first 500 chars for debugging
        preview = text[:500] if len(text) > 500 else text
        logger.debug(f"Parsing oneshot response (length: {len(text)}, preview: {preview}...)")
        
        data = None
        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            logger.warning(f"Initial JSON parse failed: {e}, attempting to extract JSON from response")
            # Attempt to strip code fences if present
            fence_start = text.find("```")
            fence_end = text.rfind("```")
            if fence_start != -1 and fence_end != -1 and fence_end > fence_start:
                fenced = text[fence_start + 3:fence_end].strip()
                # Remove language identifier if present (e.g., ```json)
                if fenced.startswith("json"):
                    fenced = fenced[4:].strip()
                elif fenced.startswith("{"):
                    pass  # Already starts with JSON
                try:
                    data = json.loads(fenced)
                    logger.info("Successfully extracted JSON from code fence")
                except json.JSONDecodeError as e2:
                    logger.warning(f"JSON parse from code fence failed: {e2}")
                    data = None
            else:
                # Try to find JSON object in the text
                json_start = text.find("{")
                json_end = text.rfind("}")
                if json_start != -1 and json_end != -1 and json_end > json_start:
                    json_snippet = text[json_start:json_end + 1]
                    try:
                        data = json.loads(json_snippet)
                        logger.info("Successfully extracted JSON object from response")
                    except json.JSONDecodeError as e3:
                        logger.warning(f"JSON extraction failed: {e3}")
                        data = None

        if not isinstance(data, dict):
            # Log the full response for debugging (truncated if too long)
            error_preview = text[:1000] if len(text) > 1000 else text
            logger.error(f"Failed to parse oneshot response as JSON. Response preview: {error_preview}")
            raise ValueError(
                f"Claude oneshot response is not valid JSON with markdown field. "
                f"Response length: {len(text)}, starts with: {text[:100]}"
            )

        markdown = str(data.get("markdown", "")).strip()
        if not markdown:
            logger.error(f"Response parsed as JSON but missing markdown field. Keys: {list(data.keys())}")
            raise ValueError("Claude oneshot response missing 'markdown' content")

        feedback: Dict[str, Any] = {}
        fb = data.get("feedback") or {}
        if isinstance(fb, dict):
            feedback = fb

        return markdown, feedback

    def _parse_feedback_json(self, text: str) -> Dict[str, Any]:
        """Parse feedback JSON with graceful fallback."""
        import re
        
        # First try direct JSON parse
        try:
            data = json.loads(text.strip())
            return data if isinstance(data, dict) else {}
        except Exception:
            pass
        
        # Try to extract JSON from markdown code blocks (```json ... ``` or ``` ... ```)
        # Pattern matches ```json or ``` followed by content and closing ```
        patterns = [
            r'```json\s*([\s\S]*?)\s*```',  # ```json ... ```
            r'```\s*([\s\S]*?)\s*```',       # ``` ... ```
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                json_str = match.group(1).strip()
                try:
                    data = json.loads(json_str)
                    if isinstance(data, dict):
                        logger.info(f"Successfully parsed JSON from code block, keys: {list(data.keys())}")
                        return data
                except Exception as e:
                    logger.warning(f"Failed to parse JSON from code block: {e}")
                    continue
        
        # Try to find raw JSON object in text
        json_start = text.find('{')
        json_end = text.rfind('}')
        if json_start != -1 and json_end != -1 and json_end > json_start:
            try:
                data = json.loads(text[json_start:json_end + 1])
                if isinstance(data, dict):
                    return data
            except Exception:
                pass
        
        logger.warning(f"Could not parse JSON from text (first 200 chars): {text[:200]}")
        return {}

    def _parse_response(self, response_text: str) -> Dict[str, Any]:
        """Parse Claude's response into a dictionary with robust fallbacks."""
        text = response_text.strip()

        # 1) Fast path: strict JSON
        if text.startswith('{') and text.endswith('}'):
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                pass  # Fall through to other methods

        # 2) JSON fenced block ```json ... ```
        fence_start = text.find("```json")
        if fence_start != -1:
            fence_start = fence_start + len("```json")
            fence_end = text.find("```", fence_start)
            if fence_end != -1:
                fenced = text[fence_start:fence_end].strip()
                if fenced.startswith('{'):
                    try:
                        return json.loads(fenced)
                    except json.JSONDecodeError as e:
                        print(f"[WARN] JSON parse error in fenced block: {e}")
                        # Try to extract and show the problematic area
                        if hasattr(e, 'pos'):
                            start = max(0, e.pos - 100)
                            end = min(len(fenced), e.pos + 100)
                            print(f"[DEBUG] Context around error: ...{fenced[start:end]}...")
                        raise

        # 3) Last resort: slice between first '{' and last '}'
        start_idx = text.find('{')
        end_idx = text.rfind('}') + 1
        if start_idx != -1 and end_idx > start_idx:
            try:
                return json.loads(text[start_idx:end_idx])
            except json.JSONDecodeError as e:
                print(f"[WARN] JSON parse error: {e}")
                extracted = text[start_idx:end_idx]
                # Try to show context around the error
                if hasattr(e, 'pos'):
                    err_start = max(0, e.pos - 100)
                    err_end = min(len(extracted), e.pos + 100)
                    print(f"[DEBUG] Context around error: ...{extracted[err_start:err_end]}...")
                raise

        raise ValueError("No JSON object found in response")


# =============================================================================
# Standalone functions for API use
# =============================================================================

def generate_questions(scope_markdown: str) -> Dict[str, List[str]]:
    """
    Standalone function to generate questions from a scope markdown.
    Used by the API endpoints.
    """
    extractor = ClaudeVariableExtractor()
    return extractor.generate_questions(scope_markdown=scope_markdown)


def regenerate_with_answers(
    original_markdown: str,
    answers: str,
    extra_research: bool = False,
    research_provider: str = "claude",
) -> str:
    """
    Regenerate a scope document using the provided answers/context.
    
    Args:
        original_markdown: The original scope markdown to improve
        answers: Answers to questions or additional context
        extra_research: Whether to perform additional web research
        research_provider: "claude" or "perplexity" for research
        
    Returns:
        Updated markdown with improvements based on the answers
    """
    from anthropic import Anthropic
    from server.core.config import ANTHROPIC_API_KEY, CLAUDE_THINKING_BUDGET
    
    client = Anthropic(api_key=ANTHROPIC_API_KEY)
    
    logger.info(f"Regenerating scope with answers (extra_research={extra_research}, provider={research_provider})")
    
    system_prompt = """You are a senior solutions architect refining a technical scope document.

Your task is to improve the existing scope document using the provided answers and context.
Make the following types of improvements:
1. Fill in any gaps or unknowns based on the answers
2. Update technical details, timelines, or estimates if the answers provide new information
3. Add clarifications where ambiguity existed
4. Ensure consistency throughout the document

IMPORTANT:
- Keep the same overall structure and formatting as the original
- Do not remove sections unless explicitly requested
- Make targeted, precise improvements rather than rewriting everything
- Preserve all markdown formatting

Output ONLY the complete updated markdown document, no explanations."""

    user_prompt = f"""## Original Scope Document

{original_markdown}

---

## Answers and Additional Context

{answers}

---

Please generate the improved version of the scope document, incorporating the answers and context above."""

    # Determine if we should use web search
    tools = None
    if extra_research and research_provider == "claude":
        tools = [{"type": "web_search_20250305", "name": "web_search", "max_uses": 3}]
    
    try:
        # Use streaming for long operations with extended thinking
        result_text = ""
        with client.messages.stream(
            model=CLAUDE_MODEL,
            max_tokens=MAX_TOKENS,
            temperature=1,  # Must be 1 when thinking is enabled
            thinking={"type": "enabled", "budget_tokens": CLAUDE_THINKING_BUDGET},
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
            tools=tools,
        ) as stream:
            for event in stream:
                # Collect text from text delta events
                if hasattr(event, 'type') and event.type == 'content_block_delta':
                    if hasattr(event, 'delta') and hasattr(event.delta, 'text'):
                        result_text += event.delta.text
        
        if result_text:
            logger.info(f"Regeneration complete, output length: {len(result_text)}")
            return result_text.strip()
        
        raise ValueError("No text content in streamed response")
        
    except Exception as exc:
        logger.exception(f"Regeneration failed: {exc}")
        raise

