"""Add google_auth table for per-user Google OAuth tokens.

Revision ID: af2c6d2b9e0b
Revises: e3808bb9624b
Create Date: 2025-12-04 18:32:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "af2c6d2b9e0b"
down_revision: Union[str, None] = "e3808bb9624b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "google_auth",
        sa.Column("user_id", sa.UUID(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("access_token", sa.Text(), nullable=True),
        sa.Column("refresh_token", sa.Text(), nullable=True),
        sa.Column("token_expiry", sa.DateTime(timezone=False), nullable=True),
        sa.Column("scope", sa.Text(), nullable=True),
        sa.Column("state", sa.String(length=255), nullable=True),
        sa.Column("state_created_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("google_auth")


