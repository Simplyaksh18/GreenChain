"""010_mrv_soft_delete_source_types

Phase 9C:
- farms: add is_deleted (bool), deleted_at (datetime nullable)
- sensor_readings: add MANUAL, IMPORTED to source_type enum
- satellite_observations: add SATELLITE_MANUAL, SATELLITE_IMPORTED to source enum
- drone_observations: add source column (DroneSource enum)

Revision ID: 010_mrv_soft_delete_source_types
Revises: 009_add_missing_custodial_columns
"""
from alembic import op
import sqlalchemy as sa

revision = "010_mrv_soft_delete_source_types"
down_revision = "009_add_missing_custodial"
branch_labels = None
depends_on = None


def upgrade():
    # ── farms: soft-delete columns ─────────────────────────────────────────────
    with op.batch_alter_table("farms") as batch_op:
        batch_op.add_column(
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false"))
        )
        batch_op.add_column(
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True)
        )

    # ── sensor_readings: extend source_type enum ──────────────────────────────
    # SQLite does not enforce enum constraints natively, so we just alter the
    # column type to a plain String — values are validated at the ORM / schema layer.
    with op.batch_alter_table("sensor_readings") as batch_op:
        batch_op.alter_column(
            "source_type",
            type_=sa.String(length=20),
            existing_nullable=False,
        )

    # ── satellite_observations: extend source enum ─────────────────────────────
    with op.batch_alter_table("satellite_observations") as batch_op:
        batch_op.alter_column(
            "source",
            type_=sa.String(length=30),
            existing_nullable=False,
        )

    # ── drone_observations: add source column ─────────────────────────────────
    with op.batch_alter_table("drone_observations") as batch_op:
        batch_op.add_column(
            sa.Column(
                "source",
                sa.String(length=20),
                nullable=False,
                server_default="DRONE_SIMULATED",
            )
        )


def downgrade():
    with op.batch_alter_table("drone_observations") as batch_op:
        batch_op.drop_column("source")

    with op.batch_alter_table("farms") as batch_op:
        batch_op.drop_column("deleted_at")
        batch_op.drop_column("is_deleted")
