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
            return self._format_list(value)
        
        if isinstance(value, dict):
            return self._format_dict(value)
        
        if isinstance(value, str):
            return value.strip()
        
        return str(value)
    
    def _format_list(self, items: list) -> str:
        """Format a list as markdown bullet points."""
        if not items:
            return "* TBD"
        
        formatted_items = []
        for item in items:
            if isinstance(item, dict):
                # Handle nested objects
                item_str = json.dumps(item, indent=2)
            else:
                item_str = str(item).strip()
            
            formatted_items.append(f"* {item_str}")
        
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

