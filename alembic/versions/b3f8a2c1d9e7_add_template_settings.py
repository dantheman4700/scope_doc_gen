"""Add template_type to runs and settings to teams.

Revision ID: 20251208_add_template_type_and_settings
Revises: af2c6d2b9e0b
Create Date: 2025-12-08

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "b3f8a2c1d9e7"
down_revision: Union[str, None] = "af2c6d2b9e0b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add template_type column to runs table
    op.add_column(
        "runs",
        sa.Column("template_type", sa.String(50), nullable=True),
    )
    
    # Add settings column to teams table with default empty JSONB
    op.add_column(
        "teams",
        sa.Column(
            "settings",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    # Remove server_default after setting the column (keeps code default only)
    op.alter_column("teams", "settings", server_default=None)


def downgrade() -> None:
    op.drop_column("runs", "template_type")
    op.drop_column("teams", "settings")

