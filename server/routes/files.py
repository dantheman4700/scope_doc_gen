"""Project file management endpoints."""

from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from ..adapters.storage import StorageBackend
from ..dependencies import db_session, get_storage
from ..db import models


router = APIRouter(prefix="/projects/{project_id}/files", tags=["files"])


class ProjectFileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    filename: str
    size: int
    media_type: Optional[str]
    checksum: str
    created_at: datetime
    path: str


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

            record = models.ProjectFile(
                project_id=project.id,
                filename=filename,
                path=relative_path,
                size=len(contents),
                media_type=upload.content_type,
                checksum=checksum,
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

