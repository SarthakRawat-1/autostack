"""recreate_dropped_indexes

Revision ID: 007
Revises: 6230bf3fb1d6
Create Date: 2026-02-28 10:00:00.000000

Fixes migration 006 which accidentally dropped all table indexes
as an auto-generated side-effect. This migration recreates them.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '007'
down_revision: Union[str, None] = '6230bf3fb1d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Recreate all indexes that were dropped by migration 006."""

    # projects indexes
    op.create_index(op.f('ix_projects_status'), 'projects', ['status'], unique=False)
    op.create_index(op.f('ix_projects_created_at'), 'projects', ['created_at'], unique=False)

    # tasks indexes
    op.create_index(op.f('ix_tasks_project_id'), 'tasks', ['project_id'], unique=False)
    op.create_index(op.f('ix_tasks_agent_role'), 'tasks', ['agent_role'], unique=False)
    op.create_index(op.f('ix_tasks_status'), 'tasks', ['status'], unique=False)
    op.create_index(op.f('ix_tasks_priority'), 'tasks', ['priority'], unique=False)

    # workflow_states indexes
    op.create_index(op.f('ix_workflow_states_project_id'), 'workflow_states', ['project_id'], unique=False)
    op.create_index(op.f('ix_workflow_states_phase'), 'workflow_states', ['phase'], unique=False)

    # logs indexes
    op.create_index(op.f('ix_logs_project_id'), 'logs', ['project_id'], unique=False)
    op.create_index(op.f('ix_logs_level'), 'logs', ['level'], unique=False)
    op.create_index(op.f('ix_logs_created_at'), 'logs', ['created_at'], unique=False)

    # metrics indexes
    op.create_index(op.f('ix_metrics_project_id'), 'metrics', ['project_id'], unique=False)
    op.create_index(op.f('ix_metrics_metric_type'), 'metrics', ['metric_type'], unique=False)
    op.create_index(op.f('ix_metrics_created_at'), 'metrics', ['created_at'], unique=False)


def downgrade() -> None:
    """Drop the recreated indexes (returns to post-006 state)."""

    op.drop_index(op.f('ix_metrics_created_at'), table_name='metrics')
    op.drop_index(op.f('ix_metrics_metric_type'), table_name='metrics')
    op.drop_index(op.f('ix_metrics_project_id'), table_name='metrics')
    op.drop_index(op.f('ix_logs_created_at'), table_name='logs')
    op.drop_index(op.f('ix_logs_level'), table_name='logs')
    op.drop_index(op.f('ix_logs_project_id'), table_name='logs')
    op.drop_index(op.f('ix_workflow_states_phase'), table_name='workflow_states')
    op.drop_index(op.f('ix_workflow_states_project_id'), table_name='workflow_states')
    op.drop_index(op.f('ix_tasks_priority'), table_name='tasks')
    op.drop_index(op.f('ix_tasks_status'), table_name='tasks')
    op.drop_index(op.f('ix_tasks_agent_role'), table_name='tasks')
    op.drop_index(op.f('ix_tasks_project_id'), table_name='tasks')
    op.drop_index(op.f('ix_projects_created_at'), table_name='projects')
    op.drop_index(op.f('ix_projects_status'), table_name='projects')
