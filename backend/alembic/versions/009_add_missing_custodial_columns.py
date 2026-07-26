"""009_add_missing_custodial_columns

Adds missing custodial columns to carbon_tokens that were skipped when
the previous migration run was stamped in this local environment.

Revision ID: 009_add_missing_custodial_columns
Revises: 907b42f92dd8
"""
from alembic import op
import sqlalchemy as sa

revision = "009_add_missing_custodial"
down_revision = "907b42f92dd8"
branch_labels = None
depends_on = None


def upgrade():
    # Add columns only if they don't exist (idempotent)
    op.execute("""
    DO $$
    BEGIN
      IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'carbon_tokens' AND column_name = 'fpo_id'
      ) THEN
        ALTER TABLE carbon_tokens ADD COLUMN fpo_id INTEGER;
      END IF;

      IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'carbon_tokens' AND column_name = 'beneficiary_farmer_id'
      ) THEN
        ALTER TABLE carbon_tokens ADD COLUMN beneficiary_farmer_id INTEGER;
      END IF;

      IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'carbon_tokens' AND column_name = 'custodial_owner_type'
      ) THEN
        ALTER TABLE carbon_tokens ADD COLUMN custodial_owner_type VARCHAR(20) NOT NULL DEFAULT 'FPO';
      END IF;
    END$$;
    """)

    # Create foreign key constraints if missing
    op.execute("""
    DO $$
    BEGIN
      IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_carbon_tokens_fpo_id'
      ) THEN
        ALTER TABLE carbon_tokens ADD CONSTRAINT fk_carbon_tokens_fpo_id FOREIGN KEY (fpo_id) REFERENCES fpo_profiles(id);
      END IF;
      IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_carbon_tokens_beneficiary'
      ) THEN
        ALTER TABLE carbon_tokens ADD CONSTRAINT fk_carbon_tokens_beneficiary FOREIGN KEY (beneficiary_farmer_id) REFERENCES users(id);
      END IF;
    END$$;
    """)


def downgrade():
    # On downgrade, drop columns if present (safe for local dev)
    op.execute("""
    DO $$
    BEGIN
      IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'carbon_tokens' AND column_name = 'custodial_owner_type') THEN
        ALTER TABLE carbon_tokens DROP COLUMN custodial_owner_type;
      END IF;
      IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'carbon_tokens' AND column_name = 'beneficiary_farmer_id') THEN
        ALTER TABLE carbon_tokens DROP COLUMN beneficiary_farmer_id;
      END IF;
      IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'carbon_tokens' AND column_name = 'fpo_id') THEN
        ALTER TABLE carbon_tokens DROP COLUMN fpo_id;
      END IF;
    END$$;
    """)
