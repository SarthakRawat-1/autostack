"""Add source_branch column to projects table

Revision ID: 004
Revises: 003
Create Date: 2026-01-25
"""
from alembic import op
import sqlalchemy as sa

revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('projects', sa.Column('source_branch', sa.String(255), nullable=True))


def downgrade():
    op.drop_column('projects', 'source_branch')
