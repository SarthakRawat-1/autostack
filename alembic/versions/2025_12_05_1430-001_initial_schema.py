"""initial schema

Revision ID: 001
Revises: 
Create Date: 2024-12-05 14:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Create all initial tables for AutoStack
    
    Tables:
    - projects: Main project tracking
    - tasks: Individual agent tasks
    - workflow_states: LangGraph state persistence
    - logs: Application logging
    - metrics: Performance tracking
    """
    
    # Create projects table
    op.create_table(
        'projects',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('repository_url', sa.String(length=512), nullable=True),
        sa.Column('status', sa.Enum(
            'INITIALIZING', 'PLANNING', 'DEVELOPING', 'TESTING', 
            'REVIEWING', 'DOCUMENTING', 'COMPLETED', 'FAILED', 'CANCELLED',
            name='projectstatus'
        ), nullable=False),
        sa.Column('current_phase', sa.String(length=100), nullable=True),
        sa.Column('notification_channel', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_projects_status'), 'projects', ['status'], unique=False)
    op.create_index(op.f('ix_projects_created_at'), 'projects', ['created_at'], unique=False)
    
    # Create tasks table
    op.create_table(
        'tasks',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('project_id', sa.String(), nullable=False),
        sa.Column('agent_role', sa.String(length=100), nullable=False),
        sa.Column('status', sa.Enum(
            'PENDING', 'IN_PROGRESS', 'COMPLETED', 'FAILED',
            name='taskstatus'
        ), nullable=False),
        sa.Column('priority', sa.Integer(), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('requirements', sa.Text(), nullable=True),
        sa.Column('dependencies', sa.JSON(), nullable=False),
        sa.Column('result', sa.JSON(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_tasks_project_id'), 'tasks', ['project_id'], unique=False)
    op.create_index(op.f('ix_tasks_agent_role'), 'tasks', ['agent_role'], unique=False)
    op.create_index(op.f('ix_tasks_status'), 'tasks', ['status'], unique=False)
    op.create_index(op.f('ix_tasks_priority'), 'tasks', ['priority'], unique=False)
    
    # Create workflow_states table
    op.create_table(
        'workflow_states',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('project_id', sa.String(), nullable=False),
        sa.Column('state_data', sa.JSON(), nullable=False),
        sa.Column('phase', sa.String(length=100), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_workflow_states_project_id'), 'workflow_states', ['project_id'], unique=False)
    op.create_index(op.f('ix_workflow_states_phase'), 'workflow_states', ['phase'], unique=False)
    
    # Create logs table
    op.create_table(
        'logs',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('project_id', sa.String(), nullable=False),
        sa.Column('agent_role', sa.String(length=100), nullable=True),
        sa.Column('level', sa.Enum(
            'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL',
            name='loglevel'
        ), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('extra_data', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_logs_project_id'), 'logs', ['project_id'], unique=False)
    op.create_index(op.f('ix_logs_level'), 'logs', ['level'], unique=False)
    op.create_index(op.f('ix_logs_created_at'), 'logs', ['created_at'], unique=False)
    
    # Create metrics table
    op.create_table(
        'metrics',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('project_id', sa.String(), nullable=True),
        sa.Column('metric_type', sa.String(length=100), nullable=False),
        sa.Column('metric_name', sa.String(length=255), nullable=False),
        sa.Column('value', sa.Float(), nullable=False),
        sa.Column('unit', sa.String(length=50), nullable=True),
        sa.Column('extra_data', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_metrics_project_id'), 'metrics', ['project_id'], unique=False)
    op.create_index(op.f('ix_metrics_metric_type'), 'metrics', ['metric_type'], unique=False)
    op.create_index(op.f('ix_metrics_created_at'), 'metrics', ['created_at'], unique=False)


def downgrade() -> None:
    """
    Drop all tables
    """
    op.drop_index(op.f('ix_metrics_created_at'), table_name='metrics')
    op.drop_index(op.f('ix_metrics_metric_type'), table_name='metrics')
    op.drop_index(op.f('ix_metrics_project_id'), table_name='metrics')
    op.drop_table('metrics')
    
    op.drop_index(op.f('ix_logs_created_at'), table_name='logs')
    op.drop_index(op.f('ix_logs_level'), table_name='logs')
    op.drop_index(op.f('ix_logs_project_id'), table_name='logs')
    op.drop_table('logs')
    
    op.drop_index(op.f('ix_workflow_states_phase'), table_name='workflow_states')
    op.drop_index(op.f('ix_workflow_states_project_id'), table_name='workflow_states')
    op.drop_table('workflow_states')
    
    op.drop_index(op.f('ix_tasks_priority'), table_name='tasks')
    op.drop_index(op.f('ix_tasks_status'), table_name='tasks')
    op.drop_index(op.f('ix_tasks_agent_role'), table_name='tasks')
    op.drop_index(op.f('ix_tasks_project_id'), table_name='tasks')
    op.drop_table('tasks')
    
    op.drop_index(op.f('ix_projects_created_at'), table_name='projects')
    op.drop_index(op.f('ix_projects_status'), table_name='projects')
    op.drop_table('projects')
    
    # Drop enums
    sa.Enum(name='projectstatus').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='taskstatus').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='loglevel').drop(op.get_bind(), checkfirst=True)
