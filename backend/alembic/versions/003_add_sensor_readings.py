"""Add sensor_readings table

Revision ID: 003
Revises: 002
Create Date: 2026-05-31

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "sensor_readings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("farm_id", sa.Integer(), nullable=False),
        sa.Column("crop_cycle_id", sa.Integer(), nullable=False),
        sa.Column("reading_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("soil_moisture", sa.Float(), nullable=False),
        sa.Column("water_depth_cm", sa.Float(), nullable=False),
        sa.Column("temperature_c", sa.Float(), nullable=False),
        sa.Column("humidity", sa.Float(), nullable=False),
        sa.Column("rainfall_mm", sa.Float(), nullable=False),
        sa.Column("estimated_methane", sa.Float(), nullable=False),
        sa.Column("data_quality_score", sa.Float(), nullable=False),
        sa.Column(
            "source_type",
            sa.Enum("SIMULATED", name="sensorsourcetype"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["farm_id"], ["farms.id"]),
        sa.ForeignKeyConstraint(["crop_cycle_id"], ["crop_cycles.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_sensor_readings_id"), "sensor_readings", ["id"], unique=False)
    op.create_index(op.f("ix_sensor_readings_farm_id"), "sensor_readings", ["farm_id"], unique=False)
    op.create_index(op.f("ix_sensor_readings_crop_cycle_id"), "sensor_readings", ["crop_cycle_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_sensor_readings_crop_cycle_id"), table_name="sensor_readings")
    op.drop_index(op.f("ix_sensor_readings_farm_id"), table_name="sensor_readings")
    op.drop_index(op.f("ix_sensor_readings_id"), table_name="sensor_readings")
    op.drop_table("sensor_readings")
    op.execute("DROP TYPE IF EXISTS sensorsourcetype")
