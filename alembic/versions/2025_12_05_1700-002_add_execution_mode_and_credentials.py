"""add execution mode and credentials

Revision ID: 002
Revises: 001
Create Date: 2024-12-05 17:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add execution mode and user credentials fields to projects table"""
    
    # Add execution mode fields
    op.add_column('projects', sa.Column('execution_mode', sa.String(20), nullable=False, server_default='auto'))
    op.add_column('projects', sa.Column('requires_approval', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('projects', sa.Column('current_interrupt', sa.String(100), nullable=True))
    
    # Add user credentials fields
    op.add_column('projects', sa.Column('github_token', sa.Text(), nullable=True))
    op.add_column('projects', sa.Column('slack_webhook_url', sa.String(512), nullable=True))
    op.add_column('projects', sa.Column('discord_webhook_url', sa.String(512), nullable=True))
    op.add_column('projects', sa.Column('use_system_credentials', sa.Integer(), nullable=False, server_default='1'))


def downgrade() -> None:
    """Remove execution mode and user credentials fields from projects table"""
    
    # Remove execution mode fields
    op.drop_column('projects', 'execution_mode')
    op.drop_column('projects', 'requires_approval')
    op.drop_column('projects', 'current_interrupt')
    
    # Remove user credentials fields
    op.drop_column('projects', 'github_token')
    op.drop_column('projects', 'slack_webhook_url')
    op.drop_column('projects', 'discord_webhook_url')
    op.drop_column('projects', 'use_system_credentials')
