"""Add fpo_profiles, farms, crop_cycles tables

Revision ID: 002
Revises: 001
Create Date: 2026-05-31

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "002"
down_revision: Union[str, None] = 'dc13f9085d58'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── fpo_profiles ──────────────────────────────────────────────────────
    op.create_table(
        "fpo_profiles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("organization_name", sa.String(length=255), nullable=False),
        sa.Column("registration_number", sa.String(length=100), nullable=False),
        sa.Column("district", sa.String(length=100), nullable=False),
        sa.Column("state", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
        sa.UniqueConstraint("registration_number"),
    )
    op.create_index(op.f("ix_fpo_profiles_id"), "fpo_profiles", ["id"], unique=False)
    op.create_index(op.f("ix_fpo_profiles_user_id"), "fpo_profiles", ["user_id"], unique=False)

    # ── farms ─────────────────────────────────────────────────────────────
    op.create_table(
        "farms",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("farmer_id", sa.Integer(), nullable=False),
        sa.Column("fpo_id", sa.Integer(), nullable=True),
        sa.Column("farm_name", sa.String(length=255), nullable=False),
        sa.Column("land_area_acres", sa.Float(), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("village", sa.String(length=100), nullable=False),
        sa.Column("district", sa.String(length=100), nullable=False),
        sa.Column("state", sa.String(length=100), nullable=False),
        sa.Column("soil_type", sa.String(length=100), nullable=False),
        sa.Column("water_source", sa.String(length=100), nullable=False),
        sa.Column("is_approved", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["farmer_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["fpo_id"], ["fpo_profiles.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_farms_id"), "farms", ["id"], unique=False)
    op.create_index(op.f("ix_farms_farmer_id"), "farms", ["farmer_id"], unique=False)
    op.create_index(op.f("ix_farms_fpo_id"), "farms", ["fpo_id"], unique=False)

    # ── crop_cycles ───────────────────────────────────────────────────────
    op.create_table(
        "crop_cycles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("farm_id", sa.Integer(), nullable=False),
        sa.Column("crop_type", sa.String(length=100), nullable=False),
        sa.Column("season", sa.String(length=100), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("baseline_method", sa.String(length=255), nullable=False),
        sa.Column("reduction_practice", sa.String(length=255), nullable=False),
        sa.Column(
            "status",
            sa.Enum("ACTIVE", "COMPLETED", "CANCELLED", name="cropcyclestatus"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["farm_id"], ["farms.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_crop_cycles_id"), "crop_cycles", ["id"], unique=False)
    op.create_index(op.f("ix_crop_cycles_farm_id"), "crop_cycles", ["farm_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_crop_cycles_farm_id"), table_name="crop_cycles")
    op.drop_index(op.f("ix_crop_cycles_id"), table_name="crop_cycles")
    op.drop_table("crop_cycles")
    op.execute("DROP TYPE IF EXISTS cropcyclestatus")

    op.drop_index(op.f("ix_farms_fpo_id"), table_name="farms")
    op.drop_index(op.f("ix_farms_farmer_id"), table_name="farms")
    op.drop_index(op.f("ix_farms_id"), table_name="farms")
    op.drop_table("farms")

    op.drop_index(op.f("ix_fpo_profiles_user_id"), table_name="fpo_profiles")
    op.drop_index(op.f("ix_fpo_profiles_id"), table_name="fpo_profiles")
    op.drop_table("fpo_profiles")
