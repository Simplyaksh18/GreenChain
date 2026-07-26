"""012_add_bank_name_to_farmer_profiles

Phase 10A Audit Fix — add bank_name field to farmer_profiles.

Revision ID: 012_add_bank_name
Revises: 011_wallet_payout_security
Create Date: 2026-06-04
"""
from alembic import op
import sqlalchemy as sa

revision = "012_add_bank_name"
down_revision = "011_wallet_payout_security"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "farmer_profiles",
        sa.Column("bank_name", sa.String(100), nullable=True),
    )


def downgrade():
    op.drop_column("farmer_profiles", "bank_name")
