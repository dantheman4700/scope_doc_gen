"""Document ingestion module for parsing various file formats."""

from pathlib import Path
from typing import List, Dict
import re
import PyPDF2


class DocumentIngester:
    """Handles reading and parsing of various document formats."""
    
    def __init__(self):
        self.supported_formats = ['.pdf', '.txt', '.md', '.vtt']
        # Filenames to ignore in input directories (case-insensitive)
        self.ignored_filenames = { 'readme.txt' }
    
    def ingest_directory(self, directory: Path) -> List[Dict[str, str]]:
        """
        Ingest all supported documents from a directory.
        
        Args:
            directory: Path to directory containing documents
            
        Returns:
            List of dictionaries with 'filename' and 'content' keys
        """
        documents = []
        
        if not directory.exists():
            print(f"[WARN] Directory {directory} does not exist")
            return documents
        
        for file_path in directory.iterdir():
            if file_path.is_file() and file_path.suffix.lower() in self.supported_formats:
                if file_path.name.lower() in self.ignored_filenames:
                    print(f"[INFO] Skipping {file_path.name} (ignored)")
                    continue
                content = self.ingest_file(file_path)
                if content:
                    documents.append({
                        'filename': file_path.name,
                        'content': content
                    })
                    print(f"[OK] Ingested: {file_path.name}")
        
        return documents
    
    def ingest_file(self, file_path: Path) -> str:
        """
        Ingest a single file based on its format.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Extracted text content
        """
        suffix = file_path.suffix.lower()
        
        try:
            if suffix == '.pdf':
                return self._read_pdf(file_path)
            elif suffix in ['.txt', '.md']:
                return self._read_text(file_path)
            elif suffix == '.vtt':
                return self._read_vtt(file_path)
            else:
                print(f"[WARN] Unsupported file format {suffix}")
                return ""
        except Exception as e:
            print(f"[ERROR] Error reading {file_path.name}: {str(e)}")
            return ""
    
    def _read_pdf(self, file_path: Path) -> str:
        """Extract text from PDF file."""
        text = []
        
        with open(file_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            for page_num, page in enumerate(pdf_reader.pages):
                page_text = page.extract_text()
                if page_text:
                    text.append(f"--- Page {page_num + 1} ---\n{page_text}")
        
        return "\n\n".join(text)
    
    def _read_text(self, file_path: Path) -> str:
        """Read plain text or markdown file."""
        with open(file_path, 'r', encoding='utf-8') as file:
            return file.read()

    def _read_vtt(self, file_path: Path) -> str:
        """Parse a WebVTT transcript, removing timestamps and cue indices.

        Preserves speaker labels if present (e.g., "SPEAKER: text").
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.read().splitlines()

        cleaned_lines: List[str] = []

        timestamp_pattern = re.compile(r"\d{2}:\d{2}:\d{2}\.\d{3}\s+-->\s+\d{2}:\d{2}:\d{2}\.\d{3}")

        for line in lines:
            if not line:
                continue
            if line.strip().upper().startswith('WEBVTT'):
                continue
            # Skip cue numbers (lines that are only digits)
            if line.strip().isdigit():
                continue
            # Skip timestamp lines
            if timestamp_pattern.search(line):
                continue
            # Remove common vtt cue settings like "align:start position:0%"
            if 'align:' in line or 'position:' in line or 'line:' in line or 'size:' in line:
                # Often appear on the same line as text; keep text after a space if any
                parts = re.split(r"\s+(align:|position:|line:|size:)", line, maxsplit=1)
                line = parts[0].strip()
                if not line:
                    continue
            cleaned_lines.append(line.strip())

        # Merge short caption fragments by joining lines, but keep paragraph breaks
        text = " ".join(cleaned_lines)
        # Collapse multiple spaces
        text = re.sub(r"\s+", " ", text).strip()
        return text
    
    def combine_documents(self, documents: List[Dict[str, str]]) -> str:
        """
        Combine multiple documents into a single text block.
        
        Args:
            documents: List of document dictionaries
            
        Returns:
            Combined text with document separators
        """
        combined = []
        
        for doc in documents:
            separator = f"\n\n{'='*80}\n"
            separator += f"DOCUMENT: {doc['filename']}\n"
            separator += f"{'='*80}\n\n"
            combined.append(separator + doc['content'])
        
        return "\n\n".join(combined)

