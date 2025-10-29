"""LLM interaction module for variable extraction using Claude."""

import json
import time
import sys
import base64
from typing import Dict, Any, List, Tuple, Optional
from anthropic import Anthropic
from .config import (
    ANTHROPIC_API_KEY,
    CLAUDE_MODEL,
    MAX_TOKENS,
    TEMPERATURE,
    ENABLE_WEB_RESEARCH,
    WEB_SEARCH_MAX_USES,
    WEB_SEARCH_ALLOWED_DOMAINS,
)


class ClaudeExtractor:
    """Handles interaction with Claude API for variable extraction."""
    
    def __init__(self, api_key: str = None):
        """Initialize Claude client."""
        self.api_key = api_key or ANTHROPIC_API_KEY
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not found. Please set it in .env file")
        
        self.client = Anthropic(api_key=self.api_key)
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
    
    def extract_variables(
        self,
        combined_documents: str,
        variables_schema: Dict[str, Any],
        variables_guide: Dict[str, Any],
        file_context: Optional[Dict[str, str]] = None,
        attachments: Optional[List[Dict[str, Any]]] = None,
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
                    temperature=TEMPERATURE,
                    system=system_prompt,
                    messages=[
                        {"role": "user", "content": message_content}
                    ],
                    tools=self.tools or None,
                )
                response_text = response.content[0].text
                variables = self._parse_response(response_text)
                print("[OK] Variable extraction complete")
                return variables
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

    def extract_variables_with_raw(
        self,
        combined_documents: str,
        variables_schema: Dict[str, Any],
        variables_guide: Dict[str, Any],
        file_context: Optional[Dict[str, str]] = None,
        attachments: Optional[List[Dict[str, Any]]] = None,
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
                    temperature=TEMPERATURE,
                    system=system_prompt,
                    messages=[
                        {"role": "user", "content": message_content}
                    ],
                    tools=self.tools or None,
                )
                response_text = response.content[0].text
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
                temperature=TEMPERATURE,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            
            response_text = response.content[0].text.strip()
            
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
3. Follow the style guidelines exactly for each variable
4. For array variables, format them according to the markdown style specified
5. If information is not available in the documents, make reasonable inferences based on context or use "TBD" for missing critical information
6. Ensure all required fields have values
7. Return the results as a valid JSON object

ASSUMPTIONS:
1. The development labor rate is fixed at $200/hour. When interpreting or calculating development-related costs, use $200/hr unless explicit, contradictory pricing is stated in the documents.

Your response should be ONLY a JSON object with the extracted variables. Do not include any explanations or additional text."""
    
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

        prompt = (
            (context_section if context_section else "")
            + "\nHere are the documents to analyze:\n\n"
            + combined_documents
            + "\n\nPlease extract all variables from these documents according to the schema and style guide provided in the system prompt."
        )

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
                        temperature=0.1,
                        system=system,
                        messages=[{"role": "user", "content": user_chunk}],
                    )
                    part = response.content[0].text.strip()
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
    
    def _parse_response(self, response_text: str) -> Dict[str, Any]:
        """Parse Claude's response into a dictionary with robust fallbacks."""
        text = response_text.strip()

        # 1) Fast path: strict JSON
        if text.startswith('{') and text.endswith('}'):
            return json.loads(text)

        # 2) JSON fenced block ```json ... ```
        fence_start = text.find("```json")
        if fence_start != -1:
            fence_start = fence_start + len("```json")
            fence_end = text.find("```", fence_start)
            if fence_end != -1:
                fenced = text[fence_start:fence_end].strip()
                if fenced.startswith('{'):
                    return json.loads(fenced)

        # 3) Last resort: slice between first '{' and last '}'
        start_idx = text.find('{')
        end_idx = text.rfind('}') + 1
        if start_idx != -1 and end_idx > start_idx:
            return json.loads(text[start_idx:end_idx])

        raise ValueError("No JSON object found in response")

