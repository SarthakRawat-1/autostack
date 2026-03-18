"""Add project_type to projects

Revision ID: 005
Revises: 004
Create Date: 2026-01-27 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '005'
down_revision = '004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add project_type column with default value 'software'
    op.add_column('projects', sa.Column('project_type', sa.String(length=50), server_default='software', nullable=False))


def downgrade() -> None:
    op.drop_column('projects', 'project_type')
