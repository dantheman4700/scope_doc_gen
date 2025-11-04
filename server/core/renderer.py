"""Template rendering module for generating scope documents."""

import json
from pathlib import Path
from typing import Dict, Any
from datetime import datetime


class TemplateRenderer:
    """Handles rendering of scope document templates with extracted variables."""
    
    def __init__(self, template_path: Path):
        """
        Initialize renderer with template.
        
        Args:
            template_path: Path to the markdown template file
        """
        self.template_path = template_path
        self.template_content = self._load_template()
    
    def _load_template(self) -> str:
        """Load the template file."""
        with open(self.template_path, 'r', encoding='utf-8') as f:
            return f.read()
    
    def render(self, variables: Dict[str, Any]) -> str:
        """
        Render the template with provided variables.
        
        Args:
            variables: Dictionary of variable names to values
            
        Returns:
            Rendered document as string
        """
        print("\n[INFO] Rendering template...")
        
        # Start with template content
        rendered = self.template_content
        
        # Process each variable
        for var_name, var_value in variables.items():
            placeholder = f"{{{{{var_name}}}}}"
            formatted_value = self._format_value(var_value, var_name)
            rendered = rendered.replace(placeholder, formatted_value)
        
        # Check for any remaining unfilled placeholders
        remaining = self._find_remaining_placeholders(rendered)
        if remaining:
            print(f"[WARN] Unfilled placeholders: {', '.join(remaining)}")
        
        print("[OK] Template rendered successfully")
        return rendered
    
    def _format_value(self, value: Any, var_name: str) -> str:
        """
        Format a variable value according to its type.
        
        Args:
            value: The value to format
            var_name: Name of the variable (for context)
            
        Returns:
            Formatted string suitable for markdown
        """
        if value is None:
            return "TBD"
        
        if isinstance(value, list):
            return self._format_list(value, var_name)
        
        if isinstance(value, dict):
            return self._format_dict(value)
        
        if isinstance(value, str):
            text = value.strip()
            # Special handling for high_level_workflow: wrap in code block
            if var_name == 'high_level_workflow':
                return f"```\n{text}\n```"
            # Normalize and format timeline: one line per item, bold label before colon
            if var_name == 'timeline_milestones':
                return self._format_timeline(text)
            # Ensure automation scope is skimmable: numbered lines where possible
            if var_name == 'automation_scope':
                return self._format_automation_scope(text)
            # Trim verbosity for certain sections
            if var_name in {'security_considerations', 'scalability'}:
                return self._limit_sentences(text, max_sentences=3)
            # Appendices: short new line per reference; bulletize
            if var_name == 'appendices':
                return self._format_appendices(text)
            return text
        
        return str(value)
    
    def _format_list(self, items: list, var_name: str) -> str:
        """Format a list as markdown bullet points with context-aware styling."""
        if not items:
            return "* TBD"
        
        # Limit overly long lists for readability
        max_items = 5 if var_name in {"pain_points", "risks", "assumptions_requirements"} else None
        display_items = items[:max_items] if max_items else items

        formatted_items = []
        for item in display_items:
            if isinstance(item, dict):
                # Handle nested objects
                item_str = json.dumps(item, indent=2)
                formatted_items.append(f"* {item_str}")
                continue

            raw = str(item).strip()
            raw = self._sanitize_item_text(raw)

            # Context-aware bolding of heads (before '-' or ':')
            if var_name in {"tech_stack", "existing_tools_systems", "data_sources", "integration_points", "subscription_licensing_costs", "services"}:
                formatted_items.append(f"* {self._bold_head(raw)}")
            elif var_name == "stakeholders":
                formatted_items.append(f"* {self._bold_name_then_dash(raw)}")
            else:
                formatted_items.append(f"* {raw}")

        return "\n".join(formatted_items)
    
    def _format_dict(self, obj: dict) -> str:
        """Format a dictionary as markdown."""
        lines = []
        for key, value in obj.items():
            if isinstance(value, list):
                lines.append(f"**{key}:**")
                for item in value:
                    lines.append(f"* {item}")
            else:
                lines.append(f"**{key}:** {value}")
        
        return "\n".join(lines)

    # ---------- Helpers for context-aware formatting ----------

    def _bold_head(self, text: str) -> str:
        """Bold the head term before a ':' or '-' if present, else bold whole text.
        Sanitizes existing emphasis and ignores separators at string start/end.
        """
        clean = self._sanitize_item_text(text)
        # Order of preference: colon, spaced dash variants, then single dash
        seps = [":", " - ", " – ", " — ", "-"]
        for sep in seps:
            idx = clean.find(sep)
            if idx > 0 and idx < len(clean) - len(sep):
                head = self._strip_outer_emphasis(clean[:idx].strip())
                tail = clean[idx + len(sep):].strip()
                if head:
                    return f"**{head}**: {tail}"
                # Fallback if head empty: do not bold empty, return original clean
                return clean
        # No separator found; bold the whole cleaned text if non-empty
        return f"**{clean}**" if clean else text

    def _bold_name_then_dash(self, text: str) -> str:
        """For 'Name - Position' style strings, bold the name; sanitize pre-existing emphasis."""
        clean = self._sanitize_item_text(text)
        # Prefer spaced separators
        for sep in [" - ", " – ", " — ", ":"]:
            if sep in clean:
                name, rest = clean.split(sep, 1)
                name = self._strip_outer_emphasis(name.strip())
                rest = rest.strip()
                return f"**{name}** - {rest}" if name else clean
        # Fallback to single dash if appropriate and not leading
        idx = clean.find("-")
        if idx > 0 and idx < len(clean) - 1:
            name = self._strip_outer_emphasis(clean[:idx].strip())
            rest = clean[idx + 1:].strip()
            return f"**{name}** - {rest}" if name else clean
        return f"**{self._strip_outer_emphasis(clean)}**" if clean else text

    def _sanitize_item_text(self, text: str) -> str:
        """Remove leading bullets/numbering and outer emphasis/backticks."""
        t = text.lstrip()
        # Remove bullet prefixes
        for prefix in ["* ", "- ", "• ", "· "]:
            if t.startswith(prefix):
                t = t[len(prefix):]
                break
        # Remove numeric prefixes like '1. ', '1) ', '(1) '
        import re
        t = re.sub(r"^\(?\d+\)?[\.)]\s+", "", t)
        t = self._strip_outer_emphasis(t.strip())
        # Remove outer backticks
        if t.startswith("`") and t.endswith("`") and len(t) >= 2:
            t = t[1:-1].strip()
        return t

    def _strip_outer_emphasis(self, text: str) -> str:
        """Strip matching outer **, __, *, _ emphasis if they wrap the entire string."""
        t = text
        # Repeat to remove nested emphasis like ****name****
        changed = True
        while changed and t:
            changed = False
            if t.startswith("**") and t.endswith("**") and len(t) >= 4:
                t = t[2:-2].strip()
                changed = True
            if t.startswith("__") and t.endswith("__") and len(t) >= 4:
                t = t[2:-2].strip()
                changed = True
            if t.startswith("*") and t.endswith("*") and len(t) >= 2 and not t.startswith("**"):
                t = t[1:-1].strip()
                changed = True
            if t.startswith("_") and t.endswith("_") and len(t) >= 2 and not t.startswith("__"):
                t = t[1:-1].strip()
                changed = True
        return t

    def _format_timeline(self, text: str) -> str:
        """Normalize timeline into line-separated bullets and bold labels before colon."""
        # Split on newlines first; if single line with separators, split on ';'
        parts = [p.strip() for p in text.splitlines() if p.strip()]
        if len(parts) <= 1:
            parts = [p.strip() for p in text.replace("\u2022", "\n").replace(";", "\n").splitlines() if p.strip()]
        formatted = [f"* {self._bold_head(p)}" for p in parts]
        return "\n".join(formatted) if formatted else text

    def _format_automation_scope(self, text: str) -> str:
        """Ensure automation scope reads as numbered short lines."""
        parts = [p.strip() for p in text.splitlines() if p.strip()]
        if len(parts) <= 1:
            # Try splitting inline lists
            splitters = [";", "•", "·", " • ", " - "]
            for sp in splitters:
                if sp in text:
                    parts = [p.strip() for p in text.split(sp) if p.strip()]
                    break
        if not parts:
            return text
        limited = parts[:6]
        return "\n".join(f"{i+1}. {p}" for i, p in enumerate(limited))

    def _format_appendices(self, text: str) -> str:
        """Turn references into short bullets, one per line."""
        parts = [p.strip() for p in text.replace(";", "\n").splitlines() if p.strip()]
        return "\n".join(f"* {p}" for p in parts) if parts else text

    def _limit_sentences(self, text: str, max_sentences: int = 3) -> str:
        """Return only the first N sentences for brevity."""
        import re
        # Naive sentence split
        sentences = re.split(r"(?<=[.!?])\s+", text)
        return " ".join(sentences[:max_sentences]).strip()
    
    def _find_remaining_placeholders(self, rendered: str) -> list:
        """Find any placeholders that weren't filled."""
        import re
        pattern = r'\{\{(\w+)\}\}'
        matches = re.findall(pattern, rendered)
        return list(set(matches))
    
    def save(self, rendered_content: str, output_path: Path) -> None:
        """
        Save rendered document to file.
        
        Args:
            rendered_content: The rendered document content
            output_path: Path where to save the file
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(rendered_content)
        
        print(f"[OK] Saved to: {output_path}")
    
    def generate_filename(self, variables: Dict[str, Any]) -> str:
        """
        Generate a filename based on variables.
        
        Args:
            variables: Dictionary of variables
            
        Returns:
            Generated filename
        """
        client = variables.get('client_name', 'Unknown_Client')
        project = variables.get('project_name', 'Unknown_Project')
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Clean up for filename
        client = client.replace(' ', '_').replace('/', '_')
        project = project.replace(' ', '_').replace('/', '_')
        
        return f"{client}_{project}_TechScope_{timestamp}.md"

