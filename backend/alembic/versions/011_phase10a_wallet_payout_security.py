"""011_phase10a_wallet_payout_security

Phase 10A — Secure Custodial Payout UX + Wallet Privacy:
- fpo_profiles: add wallet_verified (bool), wallet_verified_at (datetime), wallet_network (str)
- farmer_profiles: add payout_details_verified (bool), payout_details_verified_at (datetime),
                   payout_verification_method (str)
- payouts: add idempotency_key (str, unique), provider_reference_id (str), completed_by (FK users)

Revision ID: 011_phase10a_wallet_payout_security
Revises: 010_mrv_soft_delete_source_types
Create Date: 2026-06-04
"""
from alembic import op
import sqlalchemy as sa

revision = "011_wallet_payout_security"
down_revision = "010_mrv_soft_delete_source_types"
branch_labels = None
depends_on = None


def upgrade():
    # ── fpo_profiles ─────────────────────────────────────────────────────────
    with op.batch_alter_table("fpo_profiles") as batch_op:
        batch_op.add_column(sa.Column("wallet_verified", sa.Boolean(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("wallet_verified_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("wallet_network", sa.String(50), nullable=True))

    # ── farmer_profiles ───────────────────────────────────────────────────────
    with op.batch_alter_table("farmer_profiles") as batch_op:
        batch_op.add_column(sa.Column("payout_details_verified", sa.Boolean(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("payout_details_verified_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("payout_verification_method", sa.String(50), nullable=True))

    # ── payouts ───────────────────────────────────────────────────────────────
    with op.batch_alter_table("payouts") as batch_op:
        batch_op.add_column(sa.Column("idempotency_key", sa.String(100), nullable=True))
        batch_op.add_column(sa.Column("provider_reference_id", sa.String(200), nullable=True))
        batch_op.add_column(sa.Column("completed_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True))
        batch_op.create_unique_constraint("uq_payouts_idempotency_key", ["idempotency_key"])


def downgrade():
    with op.batch_alter_table("payouts") as batch_op:
        batch_op.drop_constraint("uq_payouts_idempotency_key", type_="unique")
        batch_op.drop_column("completed_by")
        batch_op.drop_column("provider_reference_id")
        batch_op.drop_column("idempotency_key")

    with op.batch_alter_table("farmer_profiles") as batch_op:
        batch_op.drop_column("payout_verification_method")
        batch_op.drop_column("payout_details_verified_at")
        batch_op.drop_column("payout_details_verified")

    with op.batch_alter_table("fpo_profiles") as batch_op:
        batch_op.drop_column("wallet_network")
        batch_op.drop_column("wallet_verified_at")
        batch_op.drop_column("wallet_verified")
