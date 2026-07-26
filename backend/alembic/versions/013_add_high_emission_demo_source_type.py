"""013_add_high_emission_demo_source_type

Phase 10A — Add HIGH_EMISSION_DEMO to sensor_source_type enum.

For SQLite (test DB): no-op (SQLite doesn't enforce enum values).
For PostgreSQL (production): alters the enum type.

Revision ID: 013_high_emission_demo
Revises: 012_add_bank_name
Create Date: 2026-06-05
"""
from alembic import op
import sqlalchemy as sa

revision = "013_high_emission_demo"
down_revision = "012_add_bank_name"
branch_labels = None
depends_on = None


def upgrade():
    # PostgreSQL requires ALTER TYPE to add new enum values.
    # SQLite doesn't use native enums; the column stores VARCHAR, so no change needed.
    bind = op.get_bind()
    dialect = bind.dialect.name
    if dialect == "postgresql":
        op.execute("ALTER TYPE sensorsourcetype ADD VALUE IF NOT EXISTS 'HIGH_EMISSION_DEMO'")


def downgrade():
    # Cannot remove an enum value from PostgreSQL once added.
    # SQLite: no-op.
    pass
