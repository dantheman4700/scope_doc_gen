"""Add file metadata and run linkage columns.

Revision ID: 0002_file_run_metadata
Revises: 0001_initial
Create Date: 2025-10-31
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0002_file_run_metadata"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "project_files",
        sa.Column("token_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "project_files",
        sa.Column("is_summarized", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "project_files",
        sa.Column("summary_text", sa.Text(), nullable=True),
    )
    op.add_column(
        "project_files",
        sa.Column("is_too_large", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "project_files",
        sa.Column("pdf_page_count", sa.Integer(), nullable=True),
    )

    op.add_column(
        "runs",
        sa.Column(
            "included_file_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column(
        "runs",
        sa.Column("instructions", sa.Text(), nullable=True),
    )
    op.add_column(
        "runs",
        sa.Column(
            "extracted_variables_artifact_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("artifacts.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "runs",
        sa.Column(
            "parent_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )

    op.create_index(
        "ix_runs_parent_run_id",
        "runs",
        ["parent_run_id"],
    )
    op.create_index(
        "ix_runs_extracted_vars_artifact_id",
        "runs",
        ["extracted_variables_artifact_id"],
    )

    op.alter_column("project_files", "token_count", server_default=None)
    op.alter_column("project_files", "is_summarized", server_default=None)
    op.alter_column("project_files", "is_too_large", server_default=None)
    op.alter_column("runs", "included_file_ids", server_default=None)


def downgrade() -> None:
    op.alter_column(
        "runs",
        "included_file_ids",
        server_default=sa.text("'[]'::jsonb"),
    )
    op.alter_column(
        "project_files",
        "is_too_large",
        server_default=sa.text("false"),
    )
    op.alter_column(
        "project_files",
        "is_summarized",
        server_default=sa.text("false"),
    )
    op.alter_column(
        "project_files",
        "token_count",
        server_default="0",
    )

    op.drop_index("ix_runs_extracted_vars_artifact_id", table_name="runs")
    op.drop_index("ix_runs_parent_run_id", table_name="runs")

    op.drop_column("runs", "parent_run_id")
    op.drop_column("runs", "extracted_variables_artifact_id")
    op.drop_column("runs", "instructions")
    op.drop_column("runs", "included_file_ids")

    op.drop_column("project_files", "pdf_page_count")
    op.drop_column("project_files", "is_too_large")
    op.drop_column("project_files", "summary_text")
    op.drop_column("project_files", "is_summarized")
    op.drop_column("project_files", "token_count")

