"""Utilities for converting Markdown content to DOCX."""

from __future__ import annotations

import io
from pathlib import Path
from typing import List

from docx import Document


def markdown_to_docx_bytes(content: str) -> io.BytesIO:
	"""Convert a subset of Markdown into DOCX bytes."""
	document = Document()
	in_code_block = False
	code_buffer: List[str] = []

	def _add_runs_with_emphasis(paragraph, text: str) -> None:
		# Minimal inline markdown support: **bold**, __bold__, `code`
		import re
		parts = re.split(r"(\*\*.+?\*\*|__.+?__|`.+?`)", text)
		for part in parts:
			if not part:
				continue
			if (part.startswith("**") and part.endswith("**") and len(part) >= 4):
				run = paragraph.add_run(part[2:-2])
				run.bold = True
			elif (part.startswith("__") and part.endswith("__") and len(part) >= 4):
				run = paragraph.add_run(part[2:-2])
				run.bold = True
			elif (part.startswith("`") and part.endswith("`") and len(part) >= 2):
				# Render inline code as a plain run for now
				paragraph.add_run(part[1:-1])
			else:
				paragraph.add_run(part)

	for raw_line in content.splitlines():
		line = raw_line.rstrip("\n")
		stripped = line.strip()

		if stripped.startswith("```"):
			if in_code_block:
				paragraph = document.add_paragraph("\n".join(code_buffer) if code_buffer else "")
				paragraph.style = "Intense Quote"
				code_buffer.clear()
				in_code_block = False
			else:
				in_code_block = True
			continue

		if in_code_block:
			code_buffer.append(line)
			continue

		if not stripped:
			document.add_paragraph("")
			continue

		if stripped.startswith("#"):
			level = len(stripped) - len(stripped.lstrip("#"))
			text = stripped[level:].strip()
			level = max(1, min(level, 4))
			heading_para = document.add_heading("", level=level)
			_add_runs_with_emphasis(heading_para, text or "")
			continue

		if stripped.startswith(('- ', '* ')):
			bullet_text = stripped[2:].strip()
			bullet_para = document.add_paragraph(style="List Bullet")
			_add_runs_with_emphasis(bullet_para, bullet_text)
			continue

		if stripped.startswith(">"):
			quote_para = document.add_paragraph("")
			quote_para.style = "Intense Quote"
			_add_runs_with_emphasis(quote_para, stripped[1:].strip())
			continue

		body_para = document.add_paragraph("")
		_add_runs_with_emphasis(body_para, stripped)

	if code_buffer:
		paragraph = document.add_paragraph("\n".join(code_buffer))
		paragraph.style = "Intense Quote"

	buffer = io.BytesIO()
	document.save(buffer)
	buffer.seek(0)
	return buffer


def save_markdown_as_docx(content: str, output_path: Path) -> None:
	"""Render Markdown to a DOCX file at output_path."""
	buf = markdown_to_docx_bytes(content)
	output_path.parent.mkdir(parents=True, exist_ok=True)
	with open(output_path, "wb") as f:
		f.write(buf.read())


