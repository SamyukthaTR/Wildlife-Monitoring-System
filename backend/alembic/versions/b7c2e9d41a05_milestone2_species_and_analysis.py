"""Milestone 2: species catalog, image detections, audio classifications, analysis runs

Revision ID: b7c2e9d41a05
Revises: 386be452379f
Create Date: 2026-08-10

Adds the tables docs/schema.md reserved for the ML engines.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7c2e9d41a05'
down_revision: Union[str, None] = '386be452379f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'species',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('scientific_name', sa.String(), nullable=False),
        sa.Column('common_name', sa.String(), nullable=True),
        sa.Column('rank', sa.Enum('SPECIES', 'GENUS', 'FAMILY', 'COARSE', name='taxonrankenum'), nullable=False),
        sa.Column('species_group', sa.Enum('MAMMAL', 'BIRD', 'REPTILE', 'AMPHIBIAN', 'INSECT', 'MARINE', 'OTHER', name='speciesgroupenum'), nullable=False),
        sa.Column('taxon_class', sa.String(), nullable=True),
        sa.Column('taxon_order', sa.String(), nullable=True),
        sa.Column('taxon_family', sa.String(), nullable=True),
        sa.Column('gbif_taxon_key', sa.Integer(), nullable=True),
        sa.Column('gbif_match_type', sa.String(), nullable=True),
        sa.Column('inat_taxon_id', sa.Integer(), nullable=True),
        sa.Column('iucn_status', sa.String(), nullable=True),
        sa.Column('iucn_source', sa.String(), nullable=True),
        sa.Column('is_endangered', sa.Boolean(), nullable=False),
        sa.Column('label_source', sa.String(), nullable=True),
        sa.Column('model_label', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_species_id'), 'species', ['id'], unique=False)
    op.create_index(op.f('ix_species_scientific_name'), 'species', ['scientific_name'], unique=True)
    op.create_index(op.f('ix_species_model_label'), 'species', ['model_label'], unique=False)

    op.create_table(
        'analysis_runs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('observation_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.Enum('RUNNING', 'COMPLETED', 'FAILED', name='runstatusenum'), nullable=False),
        sa.Column('models_used', sa.String(), nullable=True),
        sa.Column('latency_ms', sa.Integer(), nullable=True),
        sa.Column('animal_count', sa.Integer(), nullable=True),
        sa.Column('quality_score', sa.Float(), nullable=True),
        sa.Column('quality_notes', sa.String(), nullable=True),
        sa.Column('error', sa.String(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['observation_id'], ['observation_log.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_analysis_runs_id'), 'analysis_runs', ['id'], unique=False)
    op.create_index(op.f('ix_analysis_runs_observation_id'), 'analysis_runs', ['observation_id'], unique=False)

    op.create_table(
        'image_detections',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('observation_id', sa.Integer(), nullable=False),
        sa.Column('species_id', sa.Integer(), nullable=True),
        sa.Column('label_raw', sa.String(), nullable=False),
        sa.Column('label_source', sa.String(), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=False),
        sa.Column('detector_label', sa.String(), nullable=True),
        sa.Column('candidate_label', sa.String(), nullable=True),
        sa.Column('candidate_confidence', sa.Float(), nullable=True),
        sa.Column('bbox_x', sa.Integer(), nullable=True),
        sa.Column('bbox_y', sa.Integer(), nullable=True),
        sa.Column('bbox_w', sa.Integer(), nullable=True),
        sa.Column('bbox_h', sa.Integer(), nullable=True),
        sa.Column('detection_index', sa.Integer(), nullable=False),
        sa.Column('posture_hint', sa.String(), nullable=True),
        sa.Column('is_unknown', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['observation_id'], ['observation_log.id'], ),
        sa.ForeignKeyConstraint(['species_id'], ['species.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_image_detections_id'), 'image_detections', ['id'], unique=False)
    op.create_index(op.f('ix_image_detections_observation_id'), 'image_detections', ['observation_id'], unique=False)

    op.create_table(
        'audio_classifications',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('observation_id', sa.Integer(), nullable=False),
        sa.Column('species_id', sa.Integer(), nullable=True),
        sa.Column('label_raw', sa.String(), nullable=False),
        sa.Column('label_source', sa.String(), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=False),
        sa.Column('start_time_s', sa.Float(), nullable=False),
        sa.Column('end_time_s', sa.Float(), nullable=False),
        sa.Column('is_noise', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['observation_id'], ['observation_log.id'], ),
        sa.ForeignKeyConstraint(['species_id'], ['species.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_audio_classifications_id'), 'audio_classifications', ['id'], unique=False)
    op.create_index(op.f('ix_audio_classifications_observation_id'), 'audio_classifications', ['observation_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_audio_classifications_observation_id'), table_name='audio_classifications')
    op.drop_index(op.f('ix_audio_classifications_id'), table_name='audio_classifications')
    op.drop_table('audio_classifications')

    op.drop_index(op.f('ix_image_detections_observation_id'), table_name='image_detections')
    op.drop_index(op.f('ix_image_detections_id'), table_name='image_detections')
    op.drop_table('image_detections')

    op.drop_index(op.f('ix_analysis_runs_observation_id'), table_name='analysis_runs')
    op.drop_index(op.f('ix_analysis_runs_id'), table_name='analysis_runs')
    op.drop_table('analysis_runs')

    op.drop_index(op.f('ix_species_model_label'), table_name='species')
    op.drop_index(op.f('ix_species_scientific_name'), table_name='species')
    op.drop_index(op.f('ix_species_id'), table_name='species')
    op.drop_table('species')

    sa.Enum(name='runstatusenum').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='speciesgroupenum').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='taxonrankenum').drop(op.get_bind(), checkfirst=True)
