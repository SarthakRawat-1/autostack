"""Add system_settings table

Create system_settings table for BYOK (Bring Your Own Keys) configuration.

Revision ID: 003
Revises: 002
Create Date: 2026-01-01
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'system_settings',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('groq_api_key', sa.Text(), nullable=True),
        sa.Column('openrouter_api_key', sa.Text(), nullable=True),
        sa.Column('github_token', sa.Text(), nullable=True),
        sa.Column('slack_webhook_url', sa.String(512), nullable=True),
        sa.Column('discord_webhook_url', sa.String(512), nullable=True),
        sa.Column('is_configured', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
    )


def downgrade():
    op.drop_table('system_settings')
