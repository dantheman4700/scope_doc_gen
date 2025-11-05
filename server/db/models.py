"""SQLAlchemy ORM models for the scope document platform."""

from __future__ import annotations

from datetime import datetime
from typing import Optional, List
from uuid import UUID as UUID_t, uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pgvector.sqlalchemy import Vector as VectorType

from .session import Base


def utcnow() -> datetime:
    return datetime.utcnow()


class User(Base):
    __tablename__ = "users"

    id: Mapped[UUID_t] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utcnow, nullable=False)

    projects: Mapped[List["Project"]] = relationship("Project", back_populates="owner")


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    owner_id: Mapped[Optional[UUID_t]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    flags: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utcnow, onupdate=utcnow, nullable=False)

    owner: Mapped[Optional[User]] = relationship("User", back_populates="projects")
    files: Mapped[List["ProjectFile"]] = relationship("ProjectFile", back_populates="project", cascade="all, delete-orphan")
    runs: Mapped[List["Run"]] = relationship("Run", back_populates="project", cascade="all, delete-orphan")


class ProjectFile(Base):
    __tablename__ = "project_files"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID_t] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    path: Mapped[str] = mapped_column(Text, nullable=False)
    size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    media_type: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utcnow, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_summarized: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    summary_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_too_large: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    pdf_page_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    use_summary_for_generation: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    native_token_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    summary_token_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    project: Mapped[Project] = relationship("Project", back_populates="files")


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[UUID_t] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID_t] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    mode: Mapped[str] = mapped_column(String(20), nullable=False)
    research_mode: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utcnow, nullable=False)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=False), nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=False), nullable=True)
    params: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    result_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    included_file_ids: Mapped[List[str]] = mapped_column(JSONB, default=list, nullable=False)
    instructions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    extracted_variables_artifact_id: Mapped[Optional[UUID_t]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("artifacts.id", ondelete="SET NULL"), nullable=True
    )
    parent_run_id: Mapped[Optional[UUID_t]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("runs.id", ondelete="SET NULL"), nullable=True
    )

    project: Mapped[Project] = relationship("Project", back_populates="runs")
    steps: Mapped[List["RunStep"]] = relationship("RunStep", back_populates="run", cascade="all, delete-orphan")
    artifacts: Mapped[List["Artifact"]] = relationship(
        "Artifact",
        back_populates="run",
        cascade="all, delete-orphan",
        foreign_keys="Artifact.run_id",
    )
    parent_run: Mapped[Optional["Run"]] = relationship(
        "Run",
        remote_side="Run.id",
        backref="child_runs",
    )
    extracted_variables_artifact: Mapped[Optional["Artifact"]] = relationship(
        "Artifact",
        foreign_keys=[extracted_variables_artifact_id],
        post_update=True,
    )


class RunStep(Base):
    __tablename__ = "run_steps"

    id: Mapped[UUID_t] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    run_id: Mapped[UUID_t] = mapped_column(UUID(as_uuid=True), ForeignKey("runs.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=False), nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=False), nullable=True)
    logs: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    run: Mapped[Run] = relationship("Run", back_populates="steps")


class Artifact(Base):
    __tablename__ = "artifacts"

    id: Mapped[UUID_t] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    run_id: Mapped[UUID_t] = mapped_column(UUID(as_uuid=True), ForeignKey("runs.id", ondelete="CASCADE"), nullable=False)
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    path: Mapped[str] = mapped_column(Text, nullable=False)
    meta: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utcnow, nullable=False)

    run: Mapped[Run] = relationship(
        "Run",
        back_populates="artifacts",
        foreign_keys=[run_id],
    )


class EmbeddingRecord(Base):
    __tablename__ = "scope_embeddings"

    id: Mapped[UUID_t] = mapped_column(UUID(as_uuid=True), primary_key=True)
    project_id: Mapped[Optional[UUID_t]] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True)
    doc_kind: Mapped[str] = mapped_column(String(40), nullable=False)
    embedding: Mapped[List[float]] = mapped_column(VectorType, nullable=False)
    # 'metadata' is reserved in SQLAlchemy Declarative; map column name explicitly
    meta: Mapped[Optional[dict]] = mapped_column("metadata", JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utcnow, nullable=False)

    project: Mapped[Optional[Project]] = relationship("Project")

