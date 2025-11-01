"""Project file management endpoints."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import io
import logging
import mimetypes
from uuid import UUID
from tempfile import NamedTemporaryFile, TemporaryDirectory

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from PyPDF2 import PdfReader

from ..adapters.storage import StorageBackend
from ..core.ingest import DocumentIngester, MAX_NATIVE_PDF_BYTES, MAX_NATIVE_PDF_PAGES
from ..core.llm import ClaudeExtractor
from ..core.summarizer import FileSummarizer
from ..dependencies import db_session, get_storage
from ..db import models
from ..services.token_counter import (
    TokenCountingError,
    count_tokens_for_blocks,
    make_document_block,
    make_image_block,
    make_text_block,
)


router = APIRouter(prefix="/projects/{project_id}/files", tags=["files"])

LOGGER = logging.getLogger(__name__)

TEXT_EXTENSIONS = {".txt", ".md", ".json", ".csv", ".yaml", ".yml", ".vtt"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".tif", ".tiff"}

_DOCUMENT_INGESTER = DocumentIngester()
_FILE_SUMMARIZER: Optional[FileSummarizer] = None


class ProjectFileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    filename: str
    size: int
    media_type: Optional[str]
    checksum: str
    created_at: datetime
    path: str
    token_count: int
    is_summarized: bool
    summary_text: Optional[str] = None
    is_too_large: bool
    pdf_page_count: Optional[int] = None


async def _analyze_uploaded_file(
    *,
    filename: str,
    media_type: Optional[str],
    contents: bytes,
) -> Dict[str, object]:
    normalized_media_type = media_type or ""
    if normalized_media_type.lower() in {"application/octet-stream", "binary/octet-stream"}:
        normalized_media_type = ""

    normalized_media_type = (
        normalized_media_type
        or mimetypes.guess_type(filename)[0]
        or "application/octet-stream"
    )
    suffix = Path(filename).suffix.lower()

    pdf_page_count = None
    is_pdf = normalized_media_type == "application/pdf" or suffix == ".pdf"
    if is_pdf:
        pdf_page_count = _extract_pdf_page_count(contents)

    size = len(contents)
    is_too_large = size > MAX_NATIVE_PDF_BYTES or (is_pdf and pdf_page_count and pdf_page_count > MAX_NATIVE_PDF_PAGES)

    token_count = 0
    is_summarized = False
    summary_text: Optional[str] = None

    if not is_too_large:
        blocks = _build_token_blocks(
            filename=filename,
            media_type=normalized_media_type,
            contents=contents,
            suffix=suffix,
        )
        if blocks:
            try:
                token_count = await count_tokens_for_blocks(blocks)
            except TokenCountingError as exc:
                LOGGER.warning("Token counting failed for %s: %s", filename, exc)
                token_count = 0
        else:
            LOGGER.info("No countable content for %s; defaulting token count to 0", filename)
    else:
        summary_text = await _summarize_file_contents(filename, contents)
        if summary_text:
            is_summarized = True
            try:
                token_count = await count_tokens_for_blocks([make_text_block(summary_text)])
            except TokenCountingError as exc:
                LOGGER.warning("Token counting (summary) failed for %s: %s", filename, exc)
                token_count = max(1, len(summary_text) // 4)
        else:
            LOGGER.warning("Summary unavailable for oversized file %s", filename)

    return {
        "media_type": normalized_media_type,
        "token_count": token_count,
        "is_summarized": is_summarized,
        "summary_text": summary_text,
        "is_too_large": is_too_large,
        "pdf_page_count": pdf_page_count,
    }


def _build_token_blocks(
    *,
    filename: str,
    media_type: str,
    contents: bytes,
    suffix: str,
) -> List[Dict[str, object]]:
    if _treat_as_text(media_type, suffix):
        text = _decode_text(contents)
        if not text.strip():
            return []
        return [make_text_block(text)]

    if _treat_as_image(media_type, suffix):
        return [make_image_block(data=contents, media_type=media_type)]

    normalized_media_type = _normalize_document_media_type(media_type, suffix)
    return [make_document_block(data=contents, media_type=normalized_media_type, filename=filename)]


def _treat_as_text(media_type: str, suffix: str) -> bool:
    if media_type.startswith("text/"):
        return True
    if suffix in TEXT_EXTENSIONS:
        return True
    if media_type in {"application/json", "application/xml"}:
        return True
    return False


def _treat_as_image(media_type: str, suffix: str) -> bool:
    if media_type.startswith("image/"):
        return True
    if suffix in IMAGE_EXTENSIONS:
        return True
    return False


def _normalize_document_media_type(media_type: str, suffix: str) -> str:
    if suffix == ".pdf" or media_type in {"application/pdf", "application/x-pdf"}:
        return "application/pdf"
    return media_type


def _decode_text(contents: bytes) -> str:
    try:
        return contents.decode("utf-8")
    except UnicodeDecodeError:
        return contents.decode("latin-1", errors="ignore")


def _extract_pdf_page_count(contents: bytes) -> Optional[int]:
    try:
        pdf_reader = PdfReader(io.BytesIO(contents))
        return len(pdf_reader.pages)
    except Exception as exc:  # pragma: no cover - best effort metadata extraction
        LOGGER.warning("Unable to read PDF pages: %s", exc)
        return None


def _get_file_summarizer() -> FileSummarizer:
    global _FILE_SUMMARIZER
    if _FILE_SUMMARIZER is None:
        _FILE_SUMMARIZER = FileSummarizer(ClaudeExtractor())
    return _FILE_SUMMARIZER


async def _summarize_file_contents(filename: str, contents: bytes) -> Optional[str]:
    text = _extract_text_for_summary(filename, contents)
    if not text:
        return None

    try:
        summarizer = _get_file_summarizer()
    except Exception as exc:  # pragma: no cover - misconfiguration
        LOGGER.error("Unable to initialize file summarizer: %s", exc)
        return None
    try:
        summary = await run_in_threadpool(summarizer.summarize_file, filename, text)
    except Exception as exc:  # pragma: no cover - external API failure
        LOGGER.error("Failed to summarize %s: %s", filename, exc)
        return None

    if not summary or not summary.summary:
        return None

    try:
        return json.dumps(summary.summary, indent=2)
    except (TypeError, ValueError):
        return str(summary.summary)


def _extract_text_for_summary(filename: str, contents: bytes) -> Optional[str]:
    suffix = Path(filename).suffix or ".tmp"
    temp_path: Optional[Path] = None
    try:
        with NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(contents)
            tmp.flush()
            temp_path = Path(tmp.name)

        document = _DOCUMENT_INGESTER.ingest_file(temp_path)
    except Exception as exc:  # pragma: no cover - best effort extraction
        LOGGER.warning("Unable to ingest %s for summary: %s", filename, exc)
        return None
    finally:
        if temp_path and temp_path.exists():
            try:
                temp_path.unlink()
            except Exception:
                pass

    texts: List[str] = []
    if isinstance(document, list):
        for item in document:
            text = item.get("content") if isinstance(item, dict) else None
            if text:
                texts.append(text)
    elif isinstance(document, dict):
        text = document.get("content")
        if text:
            texts.append(text)

    combined = "\n\n".join(texts).strip()
    return combined or None


@router.get("/", response_model=List[ProjectFileResponse])
async def list_files(project_id: UUID, db: Session = Depends(db_session)) -> List[ProjectFileResponse]:
    project = _get_project(db, project_id)
    files = (
        db.query(models.ProjectFile)
        .filter(models.ProjectFile.project_id == project.id)
        .order_by(models.ProjectFile.created_at.desc())
        .all()
    )
    return [ProjectFileResponse.model_validate(file) for file in files]


@router.post("/", response_model=List[ProjectFileResponse], status_code=status.HTTP_201_CREATED)
async def upload_files(
    project_id: UUID,
    files: List[UploadFile] = File(...),
    db: Session = Depends(db_session),
    storage: StorageBackend = Depends(get_storage),
) -> List[ProjectFileResponse]:
    if not files:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No files uploaded")

    project = _get_project(db, project_id)

    records: List[models.ProjectFile] = []
    storage_keys: List[str] = []

    try:
        for upload in files:
            contents = await upload.read()
            if not contents:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Uploaded file '{upload.filename}' is empty",
                )

            filename = Path(upload.filename).name
            relative_path = f"input/{filename}"
            storage_key = _storage_key(str(project.id), relative_path)

            try:
                await run_in_threadpool(storage.put_bytes, storage_key, contents, upload.content_type)
            except Exception as exc:  # pragma: no cover - backend failure
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to save file '{filename}': {exc}",
                )

            storage_keys.append(storage_key)

            checksum = hashlib.sha256(contents).hexdigest()

            metadata = await _analyze_uploaded_file(
                filename=filename,
                media_type=upload.content_type,
                contents=contents,
            )

            record = models.ProjectFile(
                project_id=project.id,
                filename=filename,
                path=relative_path,
                size=len(contents),
                media_type=metadata["media_type"],
                checksum=checksum,
                token_count=metadata["token_count"],
                is_summarized=metadata["is_summarized"],
                summary_text=metadata.get("summary_text"),
                is_too_large=metadata["is_too_large"],
                pdf_page_count=metadata.get("pdf_page_count"),
            )
            db.add(record)
            records.append(record)

        db.commit()
    except HTTPException:
        db.rollback()
        await _cleanup_uploaded_files(storage, storage_keys)
        raise
    except Exception as exc:
        db.rollback()
        await _cleanup_uploaded_files(storage, storage_keys)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload files: {exc}",
        ) from exc

    for record in records:
        db.refresh(record)

    return [ProjectFileResponse.model_validate(record) for record in records]


@router.post("/{file_id}/summarize", response_model=ProjectFileResponse)
async def summarize_file(
    project_id: UUID,
    file_id: UUID,
    db: Session = Depends(db_session),
    storage: StorageBackend = Depends(get_storage),
) -> ProjectFileResponse:
    project = _get_project(db, project_id)
    record = (
        db.query(models.ProjectFile)
        .filter(
            models.ProjectFile.project_id == project.id,
            models.ProjectFile.id == file_id,
        )
        .one_or_none()
    )

    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    storage_key = _storage_key(str(project.id), record.path)

    with TemporaryDirectory() as tmpdir:
        destination = Path(tmpdir) / record.filename
        try:
            await run_in_threadpool(storage.download_to_path, storage_key, destination)
            contents = destination.read_bytes()
        except Exception as exc:  # pragma: no cover - storage failure
            LOGGER.error("Unable to download file %s for summarization: %s", record.filename, exc)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to download file")

    summary_text = await _summarize_file_contents(record.filename, contents)
    if not summary_text:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Unable to summarize file")

    try:
        token_count = await count_tokens_for_blocks([make_text_block(summary_text)])
    except TokenCountingError as exc:
        LOGGER.warning("Token counting (summary) failed for %s: %s", record.filename, exc)
        token_count = max(1, len(summary_text) // 4)

    record.summary_text = summary_text
    record.is_summarized = True
    record.token_count = token_count
    db.commit()
    db.refresh(record)

    return ProjectFileResponse.model_validate(record)


@router.delete("/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_file(
    project_id: UUID,
    file_id: UUID,
    db: Session = Depends(db_session),
    storage: StorageBackend = Depends(get_storage),
) -> None:
    project = _get_project(db, project_id)
    record = (
        db.query(models.ProjectFile)
        .filter(models.ProjectFile.project_id == project.id, models.ProjectFile.id == file_id)
        .one_or_none()
    )
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    storage_key = _storage_key(str(project.id), record.path)
    try:
        await run_in_threadpool(storage.delete, storage_key)
    except Exception as exc:  # pragma: no cover - backend failure
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Unable to delete file: {exc}")

    db.delete(record)
    db.commit()


def _get_project(db: Session, project_id: UUID) -> models.Project:
    project = db.get(models.Project, project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


def _storage_key(project_id: str, relative_path: str) -> str:
    clean = relative_path.lstrip("/")
    return f"projects/{project_id}/{clean}"


async def _cleanup_uploaded_files(storage: StorageBackend, storage_keys: List[str]) -> None:
    for key in storage_keys:
        try:
            await run_in_threadpool(storage.delete, key)
        except Exception:  # pragma: no cover - best effort cleanup
            pass

