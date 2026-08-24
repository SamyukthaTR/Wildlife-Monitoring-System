"""Milestone 3: habitat assessments and environmental readings

Revision ID: d4f1a7c93e56
Revises: b7c2e9d41a05
Create Date: 2026-08-24

Adds the two tables that need real persistence for Milestone 3: append-only
vegetation assessments (so habitat degradation has a real trend to measure)
and environmental readings (so a habitat page load never depends on live
network access to the weather archive -- see scripts/fetch_environment.py).
Population, conservation and ecosystem-health analytics are computed on read
from these plus the existing Milestone 1/2 tables, so they need no schema
changes of their own.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4f1a7c93e56'
down_revision: Union[str, None] = 'b7c2e9d41a05'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'habitat_assessments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('site_id', sa.Integer(), nullable=False),
        sa.Column('assessed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('images_sampled', sa.Integer(), nullable=False),
        sa.Column('vegetation_index', sa.Float(), nullable=False),
        sa.Column('green_pixel_fraction', sa.Float(), nullable=False),
        sa.Column('canopy_texture_index', sa.Float(), nullable=False),
        sa.Column('declared_habitat_type', sa.String(), nullable=True),
        sa.Column('inferred_habitat_signal', sa.String(), nullable=False),
        sa.Column('created_by', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['site_id'], ['monitoring_sites.id'], ),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_habitat_assessments_id'), 'habitat_assessments', ['id'], unique=False)
    op.create_index(op.f('ix_habitat_assessments_site_id'), 'habitat_assessments', ['site_id'], unique=False)

    op.create_table(
        'environmental_readings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('site_id', sa.Integer(), nullable=False),
        sa.Column('recorded_date', sa.Date(), nullable=False),
        sa.Column('temperature_c', sa.Float(), nullable=True),
        sa.Column('humidity_pct', sa.Float(), nullable=True),
        sa.Column('precipitation_mm', sa.Float(), nullable=True),
        sa.Column('wind_speed_kmh', sa.Float(), nullable=True),
        sa.Column('source', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['site_id'], ['monitoring_sites.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('site_id', 'recorded_date', name='uq_environmental_reading_site_date'),
    )
    op.create_index(op.f('ix_environmental_readings_id'), 'environmental_readings', ['id'], unique=False)
    op.create_index(op.f('ix_environmental_readings_site_id'), 'environmental_readings', ['site_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_environmental_readings_site_id'), table_name='environmental_readings')
    op.drop_index(op.f('ix_environmental_readings_id'), table_name='environmental_readings')
    op.drop_table('environmental_readings')

    op.drop_index(op.f('ix_habitat_assessments_site_id'), table_name='habitat_assessments')
    op.drop_index(op.f('ix_habitat_assessments_id'), table_name='habitat_assessments')
    op.drop_table('habitat_assessments')
