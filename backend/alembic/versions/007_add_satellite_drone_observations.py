"""Add satellite_observations and drone_observations tables

Revision ID: 007
Revises: 006
Create Date: 2026-06-01

Phase 7 — MRV Intelligence: stores remote-sensing data from satellite imagery
and drone surveys for cross-validation against ground sensor readings.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── satellite_observations ─────────────────────────────────────────────────
    op.create_table(
        "satellite_observations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("farm_id", sa.Integer(), sa.ForeignKey("farms.id"), nullable=False),
        sa.Column("crop_cycle_id", sa.Integer(), sa.ForeignKey("crop_cycles.id"), nullable=True),
        sa.Column("observation_date", sa.Date(), nullable=False),
        sa.Column("ndvi", sa.Float(), nullable=False),
        sa.Column("ndwi", sa.Float(), nullable=False),
        sa.Column(
            "vegetation_health",
            sa.Enum("POOR", "FAIR", "GOOD", "EXCELLENT", name="vegetationhealth"),
            nullable=False,
        ),
        sa.Column(
            "flood_risk",
            sa.Enum("NONE", "LOW", "MEDIUM", "HIGH", name="floodrisk"),
            nullable=False,
        ),
        sa.Column("cloud_cover_percent", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column(
            "source",
            sa.Enum(
                "SATELLITE_SIMULATED", "SENTINEL_2", "LANDSAT_8",
                name="satellitesource",
            ),
            nullable=False,
            server_default="SATELLITE_SIMULATED",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_satellite_observations_farm_id", "satellite_observations", ["farm_id"])
    op.create_index("ix_satellite_observations_crop_cycle_id", "satellite_observations", ["crop_cycle_id"])

    # ── drone_observations ─────────────────────────────────────────────────────
    op.create_table(
        "drone_observations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("farm_id", sa.Integer(), sa.ForeignKey("farms.id"), nullable=False),
        sa.Column("crop_cycle_id", sa.Integer(), sa.ForeignKey("crop_cycles.id"), nullable=True),
        sa.Column("observation_date", sa.Date(), nullable=False),
        sa.Column("vegetation_cover_percent", sa.Float(), nullable=False),
        sa.Column("standing_water_percent", sa.Float(), nullable=False),
        sa.Column("anomaly_score", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("image_reference", sa.String(500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_drone_observations_farm_id", "drone_observations", ["farm_id"])
    op.create_index("ix_drone_observations_crop_cycle_id", "drone_observations", ["crop_cycle_id"])


def downgrade() -> None:
    op.drop_index("ix_drone_observations_crop_cycle_id", "drone_observations")
    op.drop_index("ix_drone_observations_farm_id", "drone_observations")
    op.drop_table("drone_observations")

    op.drop_index("ix_satellite_observations_crop_cycle_id", "satellite_observations")
    op.drop_index("ix_satellite_observations_farm_id", "satellite_observations")
    op.drop_table("satellite_observations")

    op.execute("DROP TYPE IF EXISTS vegetationhealth")
    op.execute("DROP TYPE IF EXISTS floodrisk")
    op.execute("DROP TYPE IF EXISTS satellitesource")
