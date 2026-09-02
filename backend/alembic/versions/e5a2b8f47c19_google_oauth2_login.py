"""Google OAuth2 login

Revision ID: e5a2b8f47c19
Revises: d4f1a7c93e56
Create Date: 2026-09-01

Makes hashed_password nullable (Google-authenticated accounts never set one)
and adds a unique google_id so a Google sign-in can be matched back to the
same user account on repeat logins.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e5a2b8f47c19'
down_revision: Union[str, None] = 'd4f1a7c93e56'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('users', 'hashed_password', existing_type=sa.String(), nullable=True)
    op.add_column('users', sa.Column('google_id', sa.String(), nullable=True))
    op.create_index(op.f('ix_users_google_id'), 'users', ['google_id'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_users_google_id'), table_name='users')
    op.drop_column('users', 'google_id')
    op.alter_column('users', 'hashed_password', existing_type=sa.String(), nullable=False)
