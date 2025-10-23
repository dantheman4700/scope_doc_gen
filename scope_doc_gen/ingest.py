"""Document ingestion module for parsing various file formats."""

from pathlib import Path
from typing import List, Dict, Optional
import base64
import hashlib
import io
import mimetypes
import re

import PyPDF2

try:
    import fitz  # PyMuPDF
except ImportError as exc:  # pragma: no cover - handled at runtime
    fitz = None  # type: ignore

try:
    from PIL import Image
except ImportError:  # pragma: no cover - handled at runtime
    Image = None  # type: ignore

try:
    import pytesseract
except ImportError:  # pragma: no cover - handled at runtime
    pytesseract = None  # type: ignore


MAX_NATIVE_PDF_BYTES = 32 * 1024 * 1024  # 32 MB
MAX_NATIVE_PDF_PAGES = 100
SUPPORTED_IMAGE_FORMATS = {
    '.png', '.jpg', '.jpeg', '.gif', '.webp', '.tif', '.tiff'
}


class DocumentIngester:
    """Handles reading and parsing of various document formats."""

    def __init__(self):
        self.supported_formats = {'.pdf', '.txt', '.md', '.vtt'}
        # Filenames to ignore in input directories (case-insensitive)
        self.ignored_filenames = {'readme.txt'}
    
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
            if not file_path.is_file():
                continue

            suffix = file_path.suffix.lower()

            if file_path.name.lower() in self.ignored_filenames:
                print(f"[INFO] Skipping {file_path.name} (ignored)")
                continue

            if suffix in self.supported_formats:
                document = self.ingest_file(file_path)
            elif suffix in SUPPORTED_IMAGE_FORMATS:
                document = self.ingest_image(file_path)
            else:
                print(f"[WARN] Unsupported file format {suffix} for {file_path.name}")
                continue

            if document:
                documents.append(document)
                print(f"[OK] Ingested: {file_path.name}")
        
        return documents
    
    def ingest_file(self, file_path: Path) -> Optional[Dict[str, str]]:
        """
        Ingest a single file based on its format.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Document dictionary with content and metadata
        """
        suffix = file_path.suffix.lower()
        
        try:
            if suffix == '.pdf':
                return self._process_pdf(file_path)
            elif suffix in ['.txt', '.md']:
                content = self._read_text(file_path)
                return {
                    'filename': file_path.name,
                    'content': content,
                    'path': str(file_path),
                    'media_type': mimetypes.guess_type(file_path.name)[0] or 'text/plain',
                    'source_type': 'text',
                    'size_bytes': file_path.stat().st_size,
                    'upload_via': 'text',
                    'can_upload': False,
                    'content_hash': self._hash_text(content),
                }
            elif suffix == '.vtt':
                content = self._read_vtt(file_path)
                return {
                    'filename': file_path.name,
                    'content': content,
                    'path': str(file_path),
                    'media_type': 'text/vtt',
                    'source_type': 'transcript',
                    'size_bytes': file_path.stat().st_size,
                    'upload_via': 'text',
                    'can_upload': False,
                    'content_hash': self._hash_text(content),
                }
            else:
                print(f"[WARN] Unsupported file format {suffix}")
                return None
        except Exception as e:
            print(f"[ERROR] Error reading {file_path.name}: {str(e)}")
            return None

    def ingest_image(self, file_path: Path) -> Optional[Dict[str, str]]:
        """Prepare an image file for downstream processing."""

        size_bytes = file_path.stat().st_size
        media_type = mimetypes.guess_type(file_path.name)[0] or 'image/png'
        can_upload = size_bytes <= MAX_NATIVE_PDF_BYTES  # reuse 32 MB limit

        if not can_upload:
            print(f"[WARN] Image {file_path.name} exceeds upload limits ({size_bytes} bytes)")

        placeholder = f"[IMAGE] {file_path.name}"

        return {
            'filename': file_path.name,
            'content': placeholder,
            'path': str(file_path),
            'media_type': media_type,
            'source_type': 'image',
            'size_bytes': size_bytes,
            'upload_via': 'attachment' if can_upload else 'skipped',
            'can_upload': can_upload,
            'content_hash': self._hash_file(file_path),
        }

    def _process_pdf(self, file_path: Path) -> Dict[str, str]:
        """Process a PDF, choosing between native upload, text extraction, and OCR."""

        size_bytes = file_path.stat().st_size
        page_count = None
        text_content = ""
        can_upload = size_bytes <= MAX_NATIVE_PDF_BYTES

        with open(file_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            page_count = len(pdf_reader.pages)
            for page_num, page in enumerate(pdf_reader.pages):
                page_text = page.extract_text()
                if page_text:
                    text_content += f"--- Page {page_num + 1} ---\n{page_text}\n\n"

        if page_count is not None and page_count > MAX_NATIVE_PDF_PAGES:
            can_upload = False

        upload_via = 'attachment' if can_upload else 'text'

        text_content = text_content.strip()

        ocr_used = False
        if not can_upload:
            if not text_content:
                text_content = self._ocr_pdf(file_path)
                ocr_used = True
        else:
            if not text_content:
                text_content = (
                    f"[PDF] {file_path.name} (page count: {page_count or 'unknown'}) provided via native upload."
                )

        if not text_content:
            text_content = f"[PDF] {file_path.name}"

        return {
            'filename': file_path.name,
            'content': text_content,
            'path': str(file_path),
            'media_type': 'application/pdf',
            'source_type': 'pdf',
            'size_bytes': size_bytes,
            'page_count': page_count or 0,
            'upload_via': 'attachment' if can_upload else ('ocr' if ocr_used else 'text'),
            'can_upload': can_upload,
            'content_hash': self._hash_file(file_path),
        }
    
    def _read_text(self, file_path: Path) -> str:
        """Read plain text or markdown file."""
        with open(file_path, 'r', encoding='utf-8') as file:
            return file.read()

    def _ocr_pdf(self, file_path: Path) -> str:
        """Run OCR on a PDF using PyMuPDF for rendering and pytesseract for text extraction."""

        if fitz is None or pytesseract is None or Image is None:
            print("[WARN] OCR requested but PyMuPDF/Pillow/pytesseract not available")
            return ""

        try:
            doc = fitz.open(file_path)
        except Exception as exc:
            print(f"[WARN] Could not open PDF for OCR ({file_path.name}): {exc}")
            return ""

        ocr_text_parts: List[str] = []

        for page_index, page in enumerate(doc, start=1):
            try:
                pix = page.get_pixmap(dpi=200)
                img_bytes = pix.tobytes("png")
                image = Image.open(io.BytesIO(img_bytes))
                text = pytesseract.image_to_string(image)
                text = text.strip()
                if text:
                    ocr_text_parts.append(f"--- OCR Page {page_index} ---\n{text}")
            except Exception as exc:
                print(f"[WARN] OCR failed on page {page_index} of {file_path.name}: {exc}")

        doc.close()

        return "\n\n".join(ocr_text_parts)

    def _hash_text(self, text: str) -> str:
        hasher = hashlib.sha256()
        hasher.update(text.encode('utf-8', errors='ignore'))
        return hasher.hexdigest()

    def _hash_file(self, file_path: Path) -> str:
        hasher = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

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
            meta_lines = [
                f"Source type: {doc.get('source_type', 'unknown')}",
                f"Ingest method: {doc.get('upload_via', 'text')}"
            ]
            if doc.get('page_count'):
                meta_lines.append(f"Page count: {doc['page_count']}")
            if doc.get('size_bytes'):
                meta_lines.append(f"Size: {doc['size_bytes']} bytes")
            meta_block = "\n".join(meta_lines)
            combined.append(separator + meta_block + "\n\n" + doc['content'])
        
        return "\n\n".join(combined)

