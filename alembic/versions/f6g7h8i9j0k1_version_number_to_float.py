"""Change version_number from Integer to Float for sub-versions

Revision ID: f6g7h8i9j0k1
Revises: e5f6g7h8i9j0
Create Date: 2025-12-13

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'f6g7h8i9j0k1'
down_revision = 'e5f6g7h8i9j0'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Change version_number from Integer to Float to support sub-versions (1.1, 1.2, etc.)
    op.alter_column(
        'run_versions',
        'version_number',
        existing_type=sa.Integer(),
        type_=sa.Float(),
        existing_nullable=False
    )


def downgrade() -> None:
    # Change back to Integer (note: this may lose precision for sub-versions)
    op.alter_column(
        'run_versions',
        'version_number',
        existing_type=sa.Float(),
        type_=sa.Integer(),
        existing_nullable=False
    )
