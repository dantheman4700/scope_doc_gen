"""Utilities for converting Markdown content to Google Docs."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple

logger = logging.getLogger(__name__)

# Google API client types are imported for type checking and clarity.
try:
    from googleapiclient.errors import HttpError  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    HttpError = Exception  # fallback for environments without googleapiclient

# Try to import markgdoc for better markdown conversion
try:
    from markgdoc.markgdoc import process_markdown_content
    MARKGDOC_AVAILABLE = True
    logger.info("markgdoc available for enhanced markdown conversion")
except ImportError:
    MARKGDOC_AVAILABLE = False
    process_markdown_content = None
    logger.warning("markgdoc not available, using legacy markdown conversion")


def create_google_doc_from_markdown(
    content: str,
    title: str,
    drive_service,
    docs_service,
    folder_id: Optional[str] = None,
) -> str:
    """
    Create a Google Doc from markdown content using pre-authenticated clients.

    This uses markgdoc for high-quality conversion when available, with a
    fallback to the legacy custom parser.

    Args:
        content: Markdown content to convert
        title: Title for the Google Doc
        drive_service: An authenticated Drive v3 client
        docs_service: An authenticated Docs v1 client
        folder_id: Optional Google Drive folder ID to place the document in

    Returns:
        The Google Doc ID (can be used to construct a URL)
    """
    if MARKGDOC_AVAILABLE:
        return _create_with_markgdoc(content, title, drive_service, docs_service, folder_id)
    else:
        return _create_with_legacy(content, title, drive_service, docs_service, folder_id)


def _create_with_markgdoc(
    content: str,
    title: str,
    drive_service,
    docs_service,
    folder_id: Optional[str] = None,
) -> str:
    """Create Google Doc using markgdoc library for better formatting."""
    # First create an empty doc via Drive API
    file_metadata: Dict[str, Any] = {
        "name": title,
        "mimeType": "application/vnd.google-apps.document",
    }
    if folder_id:
        file_metadata["parents"] = [folder_id]

    doc_file = drive_service.files().create(body=file_metadata, fields="id, parents").execute()
    document_id = doc_file.get("id")

    if not document_id:
        raise RuntimeError("Failed to create Google Doc via Drive API")

    try:
        # Use markgdoc's process_markdown_content which handles the conversion
        # It takes the docs_service, document_id, and markdown content
        process_markdown_content(docs_service, document_id, content, debug=False)
        
        logger.info(f"Created Google Doc {document_id} using markgdoc")
        return document_id
        
    except Exception as e:
        logger.warning(f"markgdoc conversion failed, falling back to legacy: {e}")
        # Try to populate with legacy method
        try:
            requests = _parse_markdown_to_requests(content)
            if requests:
                docs_service.documents().batchUpdate(
                    documentId=document_id,
                    body={"requests": requests},
                ).execute()
        except Exception as legacy_err:
            logger.error(f"Legacy conversion also failed: {legacy_err}")
        return document_id


def _create_with_legacy(
    content: str,
    title: str,
    drive_service,
    docs_service,
    folder_id: Optional[str] = None,
) -> str:
    """Create Google Doc using legacy custom parser."""
    file_metadata: Dict[str, Any] = {
        "name": title,
        "mimeType": "application/vnd.google-apps.document",
    }
    if folder_id:
        file_metadata["parents"] = [folder_id]

    doc_file = drive_service.files().create(body=file_metadata, fields="id, parents").execute()
    document_id = doc_file.get("id")

    if not document_id:
        raise RuntimeError("Failed to create Google Doc via Drive API")

    # Parse markdown and create requests
    requests = _parse_markdown_to_requests(content)

    if requests:
        docs_service.documents().batchUpdate(
            documentId=document_id,
            body={"requests": requests},
        ).execute()

    logger.info(f"Created Google Doc {document_id} using legacy parser")
    return document_id


def _parse_markdown_to_requests(content: str) -> List[Dict[str, Any]]:
    """
    Parse markdown content into Google Docs API requests.
    
    Uses a two-pass approach: first build clean text and track formatting,
    then insert text and apply formatting.
    """
    requests: List[Dict[str, Any]] = []
    
    # Track document structure
    lines = content.splitlines()
    document_parts: List[Dict[str, Any]] = []
    
    in_code_block = False
    code_buffer: List[str] = []
    in_table = False
    table_buffer: List[str] = []
    
    def _extract_bold_ranges(text: str) -> Tuple[str, List[Tuple[int, int]]]:
        """Extract bold markers and return clean text with ranges."""
        bold_ranges: List[Tuple[int, int]] = []
        clean_text = ""
        i = 0
        
        while i < len(text):
            # Look for **text** or __text__
            match = re.search(r"\*\*(.+?)\*\*|__(.+?)__", text[i:])
            if match:
                # Add text before match
                before = text[i:i+match.start()]
                clean_text += before
                start_pos = len(clean_text)
                
                # Add bold text (without markers)
                bold_text = match.group(1) or match.group(2)
                clean_text += bold_text
                end_pos = len(clean_text)
                
                bold_ranges.append((start_pos, end_pos))
                i += match.end()
            else:
                clean_text += text[i:]
                break
        
        return clean_text, bold_ranges
    
    def _extract_italic_ranges(text: str) -> Tuple[str, List[Tuple[int, int]]]:
        """Extract italic markers and return clean text with ranges."""
        italic_ranges: List[Tuple[int, int]] = []
        clean_text = ""
        i = 0
        
        while i < len(text):
            # Look for *text* or _text_ (but not ** or __)
            match = re.search(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)|(?<!_)_(?!_)(.+?)(?<!_)_(?!_)", text[i:])
            if match:
                before = text[i:i+match.start()]
                clean_text += before
                start_pos = len(clean_text)
                
                italic_text = match.group(1) or match.group(2)
                clean_text += italic_text
                end_pos = len(clean_text)
                
                italic_ranges.append((start_pos, end_pos))
                i += match.end()
            else:
                clean_text += text[i:]
                break
        
        return clean_text, italic_ranges
    
    for line in lines:
        stripped = line.strip()
        
        # Handle code blocks
        if stripped.startswith("```"):
            if in_code_block:
                if code_buffer:
                    document_parts.append({
                        "text": "\n".join(code_buffer),
                        "type": "code"
                    })
                code_buffer.clear()
                in_code_block = False
            else:
                in_code_block = True
            continue
        
        if in_code_block:
            code_buffer.append(line)
            continue
        
        # Handle tables (convert to plain text for now)
        if stripped.startswith("|"):
            if not in_table:
                in_table = True
            table_buffer.append(stripped)
            continue
        elif in_table:
            # End of table
            if table_buffer:
                # Convert table to simple text format
                for row in table_buffer:
                    if not row.startswith("|---") and not row.startswith("| ---"):
                        cells = [c.strip() for c in row.split("|")[1:-1]]
                        if cells:
                            document_parts.append({
                                "text": " | ".join(cells),
                                "type": "paragraph",
                                "bold_ranges": []
                            })
                table_buffer.clear()
            in_table = False
        
        # Empty line
        if not stripped:
            document_parts.append({"text": "\n", "type": "paragraph"})
            continue
        
        # Headings
        if stripped.startswith("#"):
            level = len(stripped) - len(stripped.lstrip("#"))
            text = stripped[level:].strip()
            if text:
                clean_text, bold_ranges = _extract_bold_ranges(text)
                document_parts.append({
                    "text": clean_text,
                    "type": "heading",
                    "level": min(level, 6),
                    "bold_ranges": bold_ranges
                })
            continue
        
        # Numbered lists
        match = re.match(r"^(\d+)\.\s+(.+)$", stripped)
        if match:
            list_text = match.group(2).strip()
            if list_text:
                clean_text, bold_ranges = _extract_bold_ranges(list_text)
                document_parts.append({
                    "text": clean_text,
                    "type": "numbered",
                    "bold_ranges": bold_ranges
                })
            continue
        
        # Bullet points
        if stripped.startswith(("- ", "* ")):
            bullet_text = stripped[2:].strip()
            if bullet_text:
                clean_text, bold_ranges = _extract_bold_ranges(bullet_text)
                document_parts.append({
                    "text": clean_text,
                    "type": "bullet",
                    "bold_ranges": bold_ranges
                })
            continue
        
        # Block quotes
        if stripped.startswith(">"):
            quote_text = stripped[1:].strip()
            if quote_text:
                clean_text, bold_ranges = _extract_bold_ranges(quote_text)
                document_parts.append({
                    "text": clean_text,
                    "type": "paragraph",
                    "bold_ranges": bold_ranges
                })
            continue
        
        # Horizontal rules
        if stripped in ["---", "***", "___"]:
            document_parts.append({
                "text": "─" * 50,
                "type": "paragraph",
                "bold_ranges": []
            })
            continue
        
        # Regular paragraph
        clean_text, bold_ranges = _extract_bold_ranges(stripped)
        document_parts.append({
            "text": clean_text,
            "type": "paragraph",
            "bold_ranges": bold_ranges
        })
    
    # Handle any remaining code block
    if code_buffer:
        document_parts.append({
            "text": "\n".join(code_buffer),
            "type": "code"
        })
    
    # Handle any remaining table
    if table_buffer:
        for row in table_buffer:
            if not row.startswith("|---") and not row.startswith("| ---"):
                cells = [c.strip() for c in row.split("|")[1:-1]]
                if cells:
                    document_parts.append({
                        "text": " | ".join(cells),
                        "type": "paragraph",
                        "bold_ranges": []
                    })
    
    # Build full text and track formatting positions
    full_text = ""
    current_index = 1
    formatting_info: List[Dict[str, Any]] = []
    
    for part in document_parts:
        text = part["text"]
        start_index = current_index
        full_text += text + "\n"
        end_index = current_index + len(text)
        
        formatting_info.append({
            "start": start_index,
            "end": end_index,
            "type": part["type"],
            "level": part.get("level"),
            "bold_ranges": part.get("bold_ranges", []),
            "is_code": part["type"] == "code",
            "is_bullet": part["type"] == "bullet",
            "is_numbered": part["type"] == "numbered"
        })
        
        current_index += len(text) + 1  # +1 for newline
    
    # Remove trailing newline
    if full_text.endswith("\n"):
        full_text = full_text[:-1]
        current_index -= 1
    
    # Insert all text at once
    if full_text:
        requests.append({
            "insertText": {
                "location": {"index": 1},
                "text": full_text
            }
        })
    
    # Apply formatting (process in reverse to avoid index issues)
    for info in reversed(formatting_info):
        start = info["start"]
        end = info["end"]
        
        # Headings
        if info["type"] == "heading" and info["level"]:
            requests.append({
                "updateParagraphStyle": {
                    "range": {"startIndex": start, "endIndex": end},
                    "paragraphStyle": {"namedStyleType": f"HEADING_{info['level']}"},
                    "fields": "namedStyleType"
                }
            })
        
        # Bullets
        if info["is_bullet"]:
            requests.append({
                "createParagraphBullets": {
                    "range": {"startIndex": start, "endIndex": end},
                    "bulletPreset": "BULLET_DISC_CIRCLE_SQUARE"
                }
            })
        
        # Numbered lists
        if info["is_numbered"]:
            requests.append({
                "createParagraphBullets": {
                    "range": {"startIndex": start, "endIndex": end},
                    "bulletPreset": "NUMBERED_DECIMAL_NESTED"
                }
            })
        
        # Code blocks
        if info["is_code"]:
            requests.append({
                "updateTextStyle": {
                    "range": {"startIndex": start, "endIndex": end},
                    "textStyle": {
                        "weightedFontFamily": {"fontFamily": "Courier New"},
                        "backgroundColor": {"color": {"rgbColor": {"red": 0.95, "green": 0.95, "blue": 0.95}}}
                    },
                    "fields": "weightedFontFamily,backgroundColor"
                }
            })
        
        # Bold text within this part
        for bold_start, bold_end in info["bold_ranges"]:
            actual_start = start + bold_start
            actual_end = start + bold_end
            requests.append({
                "updateTextStyle": {
                    "range": {"startIndex": actual_start, "endIndex": actual_end},
                    "textStyle": {"bold": True},
                    "fields": "bold"
                }
            })
    
    return requests


def get_google_doc_url(document_id: str) -> str:
    """Get the shareable URL for a Google Doc."""
    return f"https://docs.google.com/document/d/{document_id}/edit"
