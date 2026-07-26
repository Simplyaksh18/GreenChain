"""008_custodial_model

Phase 9: Custodial carbon credit model.

Creates:
  - farmer_profiles          (payout details)
  - farmer_credit_balances   (digital-twin ledger)
  - payouts                  (simulated payout records)

Alters:
  - fpo_profiles  → adds wallet_address, vault_identifier
  - carbon_tokens → adds fpo_id, beneficiary_farmer_id, custodial_owner_type

Revision ID: 008_custodial_model
Revises: 007_add_satellite_drone_observations
"""
from alembic import op
import sqlalchemy as sa

revision = "008_custodial_model"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade():
    # Ensure required Postgres enum types exist (idempotent for local dev)
    # If these types were created by a previous partial migration run they
    # will already exist and attempting to create them again raises an error.
    op.execute("""
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'payoutmethod') THEN
    CREATE TYPE payoutmethod AS ENUM ('UPI', 'BANK_TRANSFER');
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'creditbalancestatus') THEN
    CREATE TYPE creditbalancestatus AS ENUM ('EARNED', 'TOKENIZED', 'DISTRIBUTED', 'HELD', 'CANCELLED');
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'payoutstatus') THEN
    CREATE TYPE payoutstatus AS ENUM ('INITIATED', 'PROCESSING', 'COMPLETED', 'FAILED', 'CANCELLED');
  END IF;
END$$;
""")

    # ── fpo_profiles: add custodial wallet fields ─────────────────────────────
    with op.batch_alter_table("fpo_profiles") as batch_op:
        batch_op.add_column(sa.Column("wallet_address",   sa.String(42),  nullable=True))
        batch_op.add_column(sa.Column("vault_identifier", sa.String(100), nullable=True))

    # ── carbon_tokens: add custodial relationship fields ──────────────────────
    with op.batch_alter_table("carbon_tokens") as batch_op:
        batch_op.add_column(sa.Column("fpo_id",                sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("beneficiary_farmer_id", sa.Integer(), nullable=True))
        batch_op.add_column(
            sa.Column("custodial_owner_type", sa.String(20), nullable=False, server_default="FPO")
        )
        batch_op.create_foreign_key(
            "fk_carbon_tokens_fpo_id", "fpo_profiles", ["fpo_id"], ["id"]
        )
        batch_op.create_foreign_key(
            "fk_carbon_tokens_beneficiary", "users", ["beneficiary_farmer_id"], ["id"]
        )

    # ── farmer_profiles ────────────────────────────────────────────────────────
    op.create_table(
        "farmer_profiles",
        sa.Column("id",      sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), unique=True, nullable=False),
        sa.Column(
            "preferred_payout_method",
            sa.dialects.postgresql.ENUM("UPI", "BANK_TRANSFER", name="payoutmethod", create_type=False),
            nullable=True,
        ),
        sa.Column("upi_id",                   sa.String(100), nullable=True),
        sa.Column("bank_account_holder_name", sa.String(255), nullable=True),
        sa.Column("bank_account_number",      sa.String(30),  nullable=True),
        sa.Column("ifsc_code",                sa.String(11),  nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # ── farmer_credit_balances ─────────────────────────────────────────────────
    op.create_table(
        "farmer_credit_balances",
        sa.Column("id",               sa.Integer(), primary_key=True),
        sa.Column("farmer_id",        sa.Integer(), sa.ForeignKey("users.id"),           nullable=False),
        sa.Column("fpo_id",           sa.Integer(), sa.ForeignKey("fpo_profiles.id"),    nullable=False),
        sa.Column("carbon_report_id", sa.Integer(), sa.ForeignKey("carbon_reports.id"),  nullable=False, unique=True),
        sa.Column("carbon_token_id",  sa.Integer(), sa.ForeignKey("carbon_tokens.id"),   nullable=True),
        sa.Column("credits_earned",       sa.Integer(), nullable=False, server_default="0"),
        sa.Column("credits_distributed",  sa.Integer(), nullable=False, server_default="0"),
        sa.Column("credits_available",    sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "status",
            sa.dialects.postgresql.ENUM(
                "EARNED", "TOKENIZED", "DISTRIBUTED", "HELD", "CANCELLED",
                name="creditbalancestatus", create_type=False
            ),
            nullable=False,
            server_default="EARNED",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # ── payouts ────────────────────────────────────────────────────────────────
    op.create_table(
        "payouts",
        sa.Column("id",                sa.Integer(), primary_key=True),
        sa.Column("farmer_id",         sa.Integer(), sa.ForeignKey("users.id"),                      nullable=False),
        sa.Column("fpo_id",            sa.Integer(), sa.ForeignKey("fpo_profiles.id"),               nullable=False),
        sa.Column("credit_balance_id", sa.Integer(), sa.ForeignKey("farmer_credit_balances.id"),     nullable=False),
        sa.Column("amount_credits",    sa.Integer(), nullable=False),
        sa.Column("price_per_credit",  sa.Integer(), nullable=False),
        sa.Column("payout_amount",     sa.Integer(), nullable=False),
        sa.Column("currency",          sa.String(10), nullable=False, server_default="INR"),
        sa.Column("payout_method",     sa.String(50), nullable=True),
        sa.Column(
            "status",
            sa.dialects.postgresql.ENUM(
                "INITIATED", "PROCESSING", "COMPLETED", "FAILED", "CANCELLED",
                name="payoutstatus", create_type=False
            ),
            nullable=False,
            server_default="INITIATED",
        ),
        sa.Column("initiated_by",  sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "initiated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("remarks",      sa.String(500), nullable=True),
    )


def downgrade():
    op.drop_table("payouts")
    op.drop_table("farmer_credit_balances")
    op.drop_table("farmer_profiles")
    with op.batch_alter_table("carbon_tokens") as batch_op:
        batch_op.drop_constraint("fk_carbon_tokens_fpo_id",    type_="foreignkey")
        batch_op.drop_constraint("fk_carbon_tokens_beneficiary", type_="foreignkey")
        batch_op.drop_column("custodial_owner_type")
        batch_op.drop_column("beneficiary_farmer_id")
        batch_op.drop_column("fpo_id")
    with op.batch_alter_table("fpo_profiles") as batch_op:
        batch_op.drop_column("vault_identifier")
        batch_op.drop_column("wallet_address")
