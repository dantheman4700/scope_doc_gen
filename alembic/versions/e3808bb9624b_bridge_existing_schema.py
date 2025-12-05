"""Bridge revision to align Alembic with existing database state.

This revision matches an already-applied schema state in the database where
the alembic_version table contains 'e3808bb9624b', but the corresponding
revision script was missing from the codebase.

No schema changes are performed here; it simply restores the revision node
so future migrations can build on top of it.

Revision ID: e3808bb9624b
Revises: ced154280696
Create Date: 2025-12-04 18:30:00.000000
"""

from typing import Sequence, Union

from alembic import op  # noqa: F401
import sqlalchemy as sa  # noqa: F401

# revision identifiers, used by Alembic.
revision: str = "e3808bb9624b"
down_revision: Union[str, None] = "ced154280696"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # No-op: database schema already reflects this state.
    pass


def downgrade() -> None:
    # No-op: kept for graph completeness; does not modify schema.
    pass


