"""014_create_dronesource_enum

Phase 10A repair: create the 'dronesource' PostgreSQL enum type that was
never created in migration 007.

ROOT CAUSE
----------
Migration 007 (Phase 7) created satellite_observations with a native
PostgreSQL enum type 'satellitesource', but created drone_observations
WITHOUT a source column at all.

Migration 010 (Phase 9C) later added drone_observations.source as a
VARCHAR(20) column (not a native enum). However the Python model
DroneObservation.source used SAEnum(DroneSource) with native_enum=True
(SQLAlchemy default), which causes PostgreSQL to emit ::dronesource casts
in every INSERT. Because 'dronesource' never existed in pg_type, every
INSERT into drone_observations failed with:

    psycopg2.errors.UndefinedObject: type "dronesource" does not exist

This caused the entire mrv/demo/high-emission transaction to roll back,
leaving all counts at zero despite returning HTTP 201.

FIXES APPLIED IN THIS RELEASE
------------------------------
1. drone_observation.py:   SAEnum(DroneSource, native_enum=False)
   - SQLAlchemy no longer emits ::dronesource casts; column treated as VARCHAR
2. satellite_observation.py: native_enum=False on all SAEnum columns
   - Consistent with what migration 010 did (converted columns to VARCHAR)
3. This migration: creates dronesource type in PostgreSQL as a safety net
   - Idempotent (uses DO $$ block to check pg_type before CREATE TYPE)
   - Does NOT touch existing column data
   - SQLite: no-op

Revision ID: 014_create_dronesource_enum
Revises: 013_high_emission_demo
Create Date: 2026-06-05
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision = "014_create_dronesource_enum"
down_revision = "013_high_emission_demo"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        # Create the dronesource enum type if it does not already exist.
        # PostgreSQL 9.3+ doesn't support "CREATE TYPE IF NOT EXISTS", so
        # we use a PL/pgSQL DO block to check pg_type first.
        bind.execute(text("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_type WHERE typname = 'dronesource'
                ) THEN
                    CREATE TYPE dronesource AS ENUM (
                        'DRONE_SIMULATED',
                        'DRONE_MANUAL',
                        'DRONE_IMPORTED'
                    );
                END IF;
            END
            $$;
        """))

        # Fix 10A: Convert satellite enum columns to VARCHAR to prevent DatatypeMismatch
        op.execute(text("ALTER TABLE satellite_observations ALTER COLUMN vegetation_health TYPE VARCHAR(50) USING vegetation_health::text"))
        op.execute(text("ALTER TABLE satellite_observations ALTER COLUMN flood_risk TYPE VARCHAR(50) USING flood_risk::text"))

        # Fix 10B: Add farm_status column to farms table if missing
        bind.execute(text("""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='farms' AND column_name='farm_status') THEN
                    ALTER TABLE farms ADD COLUMN farm_status VARCHAR(50) DEFAULT 'ACTIVE';
                END IF;
            END
            $$;
        """))

    # SQLite: no-op — SQLite stores all enum values as VARCHAR natively.


def downgrade():
    # Intentionally no-op: dropping an enum type that may be referenced by
    # existing rows would be destructive. The dronesource type was never part
    # of the formal column DDL (the column is VARCHAR), so leaving it in place
    # is safe.
    pass
