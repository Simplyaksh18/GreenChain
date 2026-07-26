"""015_phase11_farm_crop_lifecycle

Phase 11 — Farm Lifecycle & Crop Cycle Lifecycle columns.

Changes
-------
farms table:
  - farm_status          VARCHAR(20)  DEFAULT 'DRAFT'
  - approved_at          TIMESTAMP WITH TIME ZONE  NULL
  - approved_by          INTEGER  NULL  FK→users.id
  - archived_at          TIMESTAMP WITH TIME ZONE  NULL
  - archive_reason       VARCHAR(500)  NULL
  - farm_boundary_geojson TEXT  NULL   (GIS readiness)
  - boundary_area_hectares FLOAT  NULL
  - boundary_area_acres    FLOAT  NULL

crop_cycles table:
  - harvest_date   DATE   NULL
  - closed_at      TIMESTAMP WITH TIME ZONE  NULL
  - yield_quantity FLOAT  NULL
  - yield_unit     VARCHAR(50)  NULL

IDEMPOTENT: uses IF NOT EXISTS for all ADD COLUMN statements so the migration
is safe to re-run if columns were partially applied in a previous attempt.

Revision ID: 015_phase11_farm_crop_lifecycle
Revises: 014_create_dronesource_enum
Create Date: 2026-06-05
"""
from alembic import op
import sqlalchemy as sa

revision = "015_phase11_farm_crop_lifecycle"
down_revision = "014_create_dronesource_enum"
branch_labels = None
depends_on = None


def _col_exists(bind, table: str, column: str) -> bool:
    """Return True if column already exists in the table."""
    result = bind.execute(sa.text(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_name = :t AND column_name = :c"
    ), {"t": table, "c": column}).fetchone()
    return result is not None


def upgrade():
    bind = op.get_bind()
    dialect = bind.dialect.name

    # ── farms — add only missing columns ──────────────────────────────────────
    farm_cols = [
        ("farm_status",            "VARCHAR(20) NOT NULL DEFAULT 'DRAFT'"),
        ("approved_at",            "TIMESTAMPTZ"),
        ("approved_by",            "INTEGER"),
        ("archived_at",            "TIMESTAMPTZ"),
        ("archive_reason",         "VARCHAR(500)"),
        ("farm_boundary_geojson",  "TEXT"),
        ("boundary_area_hectares", "DOUBLE PRECISION"),
        ("boundary_area_acres",    "DOUBLE PRECISION"),
    ]

    if dialect == "postgresql":
        for col_name, col_def in farm_cols:
            if not _col_exists(bind, "farms", col_name):
                bind.execute(sa.text(
                    f"ALTER TABLE farms ADD COLUMN {col_name} {col_def}"
                ))
        # Backfill farm_status only where it is still DRAFT but is_approved = true
        bind.execute(sa.text(
            "UPDATE farms SET farm_status = 'APPROVED' "
            "WHERE is_approved = TRUE AND farm_status = 'DRAFT'"
        ))
    else:
        # SQLite path — batch_alter_table for SQLite compatibility
        with op.batch_alter_table("farms") as batch_op:
            for col_name, _ in farm_cols:
                if not _col_exists(bind, "farms", col_name):
                    if col_name == "farm_status":
                        batch_op.add_column(sa.Column(
                            col_name, sa.String(20), nullable=False, server_default="DRAFT"
                        ))
                    elif col_name in ("approved_at", "archived_at", "closed_at"):
                        batch_op.add_column(sa.Column(col_name, sa.DateTime(timezone=True), nullable=True))
                    elif col_name in ("approved_by",):
                        batch_op.add_column(sa.Column(col_name, sa.Integer, nullable=True))
                    elif col_name in ("archive_reason",):
                        batch_op.add_column(sa.Column(col_name, sa.String(500), nullable=True))
                    elif col_name in ("farm_boundary_geojson",):
                        batch_op.add_column(sa.Column(col_name, sa.Text, nullable=True))
                    else:
                        batch_op.add_column(sa.Column(col_name, sa.Float, nullable=True))

        bind.execute(sa.text(
            "UPDATE farms SET farm_status = CASE WHEN is_approved = 1 THEN 'APPROVED' ELSE 'DRAFT' END "
            "WHERE farm_status = 'DRAFT' AND is_approved = 1"
        ))

    # ── crop_cycles — add only missing columns ────────────────────────────────
    cycle_cols = [
        ("harvest_date",   "DATE"),
        ("closed_at",      "TIMESTAMPTZ"),
        ("yield_quantity", "DOUBLE PRECISION"),
        ("yield_unit",     "VARCHAR(50)"),
    ]

    if dialect == "postgresql":
        for col_name, col_def in cycle_cols:
            if not _col_exists(bind, "crop_cycles", col_name):
                bind.execute(sa.text(
                    f"ALTER TABLE crop_cycles ADD COLUMN {col_name} {col_def}"
                ))
        # Convert status column from native enum to VARCHAR if needed
        result = bind.execute(sa.text(
            "SELECT data_type FROM information_schema.columns "
            "WHERE table_name='crop_cycles' AND column_name='status'"
        )).fetchone()
        if result and result[0] == "USER-DEFINED":
            bind.execute(sa.text(
                "ALTER TABLE crop_cycles ALTER COLUMN status TYPE VARCHAR(20) USING status::text"
            ))
    else:
        with op.batch_alter_table("crop_cycles") as batch_op:
            if not _col_exists(bind, "crop_cycles", "harvest_date"):
                batch_op.add_column(sa.Column("harvest_date", sa.Date, nullable=True))
            if not _col_exists(bind, "crop_cycles", "closed_at"):
                batch_op.add_column(sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True))
            if not _col_exists(bind, "crop_cycles", "yield_quantity"):
                batch_op.add_column(sa.Column("yield_quantity", sa.Float, nullable=True))
            if not _col_exists(bind, "crop_cycles", "yield_unit"):
                batch_op.add_column(sa.Column("yield_unit", sa.String(50), nullable=True))


def downgrade():
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "postgresql":
        for col in ["yield_unit", "yield_quantity", "closed_at", "harvest_date"]:
            if _col_exists(bind, "crop_cycles", col):
                bind.execute(sa.text(f"ALTER TABLE crop_cycles DROP COLUMN IF EXISTS {col}"))
        for col in ["boundary_area_acres", "boundary_area_hectares", "farm_boundary_geojson",
                    "archive_reason", "archived_at", "approved_by", "approved_at", "farm_status"]:
            if _col_exists(bind, "farms", col):
                bind.execute(sa.text(f"ALTER TABLE farms DROP COLUMN IF EXISTS {col}"))
    else:
        with op.batch_alter_table("crop_cycles") as batch_op:
            batch_op.drop_column("yield_unit")
            batch_op.drop_column("yield_quantity")
            batch_op.drop_column("closed_at")
            batch_op.drop_column("harvest_date")
        with op.batch_alter_table("farms") as batch_op:
            batch_op.drop_column("boundary_area_acres")
            batch_op.drop_column("boundary_area_hectares")
            batch_op.drop_column("farm_boundary_geojson")
            batch_op.drop_column("archive_reason")
            batch_op.drop_column("archived_at")
            batch_op.drop_column("approved_by")
            batch_op.drop_column("approved_at")
            batch_op.drop_column("farm_status")
