"""Add soc_measurements and soc_reports tables (Phase 12.5 — additive only)

Revision ID: 2b2eecf4af1a
Revises: 016_normalize_farm_status_values
Create Date: 2026-06-06 23:26:35.570614

ADDITIVE ONLY — this migration creates two new tables.
It does NOT alter any existing table, enum, index, or constraint.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

# revision identifiers
revision: str = '2b2eecf4af1a'
down_revision: Union[str, None] = '016_normalize_farm_status_values'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _existing_tables() -> set:
    bind = op.get_bind()
    inspector = inspect(bind)
    return set(inspector.get_table_names())


def upgrade() -> None:
    tables = _existing_tables()

    # ── soc_measurements ──────────────────────────────────────────────────────
    if 'soc_measurements' not in tables:
        op.create_table(
            'soc_measurements',
            sa.Column('id',               sa.Integer(),  nullable=False),
            sa.Column('farm_id',          sa.Integer(),  nullable=False),
            sa.Column('crop_cycle_id',    sa.Integer(),  nullable=True),
            sa.Column('soc_percent',      sa.Float(),    nullable=False),
            sa.Column(
                'soc_source',
                sa.Enum(
                    'LAB', 'MANUAL', 'COPERNICUS', 'BHUVAN', 'ESTIMATED',
                    name='socsource',
                    native_enum=False,   # stored as VARCHAR — no PG enum type created
                ),
                nullable=False,
            ),
            sa.Column('confidence_score', sa.Float(),    nullable=False),
            sa.Column('notes',            sa.Text(),     nullable=True),
            sa.Column('created_at',       sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at',       sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(['farm_id'],       ['farms.id']),
            sa.ForeignKeyConstraint(['crop_cycle_id'], ['crop_cycles.id']),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_soc_measurements_id',            'soc_measurements', ['id'],            unique=False)
        op.create_index('ix_soc_measurements_farm_id',       'soc_measurements', ['farm_id'],       unique=False)
        op.create_index('ix_soc_measurements_crop_cycle_id', 'soc_measurements', ['crop_cycle_id'], unique=False)

    # ── soc_reports ───────────────────────────────────────────────────────────
    if 'soc_reports' not in tables:
        op.create_table(
            'soc_reports',
            sa.Column('id',               sa.Integer(),         nullable=False),
            sa.Column('farm_id',          sa.Integer(),         nullable=False),
            sa.Column('crop_cycle_id',    sa.Integer(),         nullable=False),
            sa.Column('baseline_soc',     sa.Float(),           nullable=False),
            sa.Column('current_soc',      sa.Float(),           nullable=False),
            sa.Column('soc_gain',         sa.Float(),           nullable=False),
            sa.Column('soc_co2e',         sa.Float(),           nullable=False),
            sa.Column('soc_credits',      sa.Integer(),         nullable=False),
            sa.Column('confidence_score', sa.Float(),           nullable=False),
            sa.Column('sources_used',     sa.String(length=255),nullable=False),
            sa.Column('methodology',      sa.Text(),            nullable=True),
            sa.Column('created_at',       sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(['farm_id'],       ['farms.id']),
            sa.ForeignKeyConstraint(['crop_cycle_id'], ['crop_cycles.id']),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_soc_reports_id',            'soc_reports', ['id'],            unique=False)
        op.create_index('ix_soc_reports_farm_id',       'soc_reports', ['farm_id'],       unique=False)
        op.create_index('ix_soc_reports_crop_cycle_id', 'soc_reports', ['crop_cycle_id'], unique=False)


def downgrade() -> None:
    tables = _existing_tables()

    if 'soc_reports' in tables:
        op.drop_index('ix_soc_reports_crop_cycle_id', table_name='soc_reports')
        op.drop_index('ix_soc_reports_farm_id',       table_name='soc_reports')
        op.drop_index('ix_soc_reports_id',            table_name='soc_reports')
        op.drop_table('soc_reports')

    if 'soc_measurements' in tables:
        op.drop_index('ix_soc_measurements_crop_cycle_id', table_name='soc_measurements')
        op.drop_index('ix_soc_measurements_farm_id',       table_name='soc_measurements')
        op.drop_index('ix_soc_measurements_id',            table_name='soc_measurements')
        op.drop_table('soc_measurements')
