"""Add users table and user_id to projects and system_settings

Revision ID: 008
Revises: 007
Create Date: 2026-03-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
import uuid

# revision identifiers, used by Alembic.
revision = '008'
down_revision = '007'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create users table
    op.create_table(
        'users',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('password_hash', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email'),
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)

    # Create a default user for existing data
    default_user_id = str(uuid.uuid4())
    op.execute(
        sa.text(
            "INSERT INTO users (id, email, name, password_hash, created_at) "
            "VALUES (:id, :email, :name, :password_hash, now())"
        ).bindparams(
            id=default_user_id,
            email="admin@autostack.local",
            name="Admin",
            # bcrypt hash of "changeme" — user should change password after migration
            password_hash="$2b$12$j.OWYlgLClPyuYKgy/y1ke82RvFqnya9YVmXj48Pn0AO27X3Huto2",
        )
    )

    # Add user_id to projects (nullable first, then backfill, then make non-null)
    op.add_column('projects', sa.Column('user_id', sa.String(), nullable=True))
    op.execute(sa.text(f"UPDATE projects SET user_id = '{default_user_id}' WHERE user_id IS NULL"))
    op.alter_column('projects', 'user_id', nullable=False)
    op.create_foreign_key('fk_projects_user_id', 'projects', 'users', ['user_id'], ['id'], ondelete='CASCADE')
    op.create_index(op.f('ix_projects_user_id'), 'projects', ['user_id'], unique=False)

    # Add user_id to system_settings (nullable first, then backfill, then make non-null)
    op.add_column('system_settings', sa.Column('user_id', sa.String(), nullable=True))
    op.execute(sa.text(f"UPDATE system_settings SET user_id = '{default_user_id}' WHERE user_id IS NULL"))
    op.alter_column('system_settings', 'user_id', nullable=False)
    op.create_foreign_key('fk_system_settings_user_id', 'system_settings', 'users', ['user_id'], ['id'], ondelete='CASCADE')
    op.create_index(op.f('ix_system_settings_user_id'), 'system_settings', ['user_id'], unique=True)

    # Drop the now-unused google_api_key column
    op.drop_column('system_settings', 'google_api_key')


def downgrade() -> None:
    # Add back google_api_key
    op.add_column('system_settings', sa.Column('google_api_key', sa.Text(), nullable=True))

    # Remove user_id from system_settings
    op.drop_index(op.f('ix_system_settings_user_id'), table_name='system_settings')
    op.drop_constraint('fk_system_settings_user_id', 'system_settings', type_='foreignkey')
    op.drop_column('system_settings', 'user_id')

    # Remove user_id from projects
    op.drop_index(op.f('ix_projects_user_id'), table_name='projects')
    op.drop_constraint('fk_projects_user_id', 'projects', type_='foreignkey')
    op.drop_column('projects', 'user_id')

    # Drop users table
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_table('users')
