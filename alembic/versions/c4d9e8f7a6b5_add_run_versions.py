"""Add run_versions table and google_tokens to users

Revision ID: c4d9e8f7a6b5
Revises: b3f8a2c1d9e7
Create Date: 2025-12-08

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'c4d9e8f7a6b5'
down_revision = 'b3f8a2c1d9e7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add google_tokens column to users table
    op.add_column('users', sa.Column('google_tokens', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    
    # Create run_versions table
    op.create_table(
        'run_versions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('run_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('runs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('version_number', sa.Integer(), nullable=False),
        sa.Column('markdown', sa.Text(), nullable=True),
        sa.Column('feedback', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('questions_for_expert', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('questions_for_client', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('graphic_path', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('regen_context', sa.Text(), nullable=True),
    )
    
    # Create index on run_id for efficient lookups
    op.create_index('ix_run_versions_run_id', 'run_versions', ['run_id'])


def downgrade() -> None:
    op.drop_index('ix_run_versions_run_id', 'run_versions')
    op.drop_table('run_versions')
    op.drop_column('users', 'google_tokens')

