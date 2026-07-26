"""Phase 17 — razorpay_payments table.

Creates:
  - razorpaypaymentpurpose enum  (FARMER_PAYOUT, MARKETPLACE_ORDER)
  - razorpaypaymentstatus  enum  (CREATED, COMPLETED, FAILED)
  - razorpay_payments table

Idempotent: IF NOT EXISTS guards + pg_type existence checks for enums.

Revision ID: 021_razorpay_payments
Revises: 020_phase16_marketplace
Create Date: 2026-06-10
"""
from __future__ import annotations
from typing import Union

from alembic import op
import sqlalchemy as sa

revision: str  = "021_razorpay_payments"
down_revision: Union[str, None] = "020_phase16_marketplace"
branch_labels = None
depends_on    = None


def _enum_exists(connection, name: str) -> bool:
    result = connection.execute(
        sa.text("SELECT 1 FROM pg_type WHERE typname = :n"),
        {"n": name},
    )
    return result.fetchone() is not None


def upgrade() -> None:
    bind = op.get_bind()
    is_pg = bind.dialect.name == "postgresql"

    if is_pg:
        if not _enum_exists(bind, "razorpaypaymentpurpose"):
            op.execute("CREATE TYPE razorpaypaymentpurpose AS ENUM ('FARMER_PAYOUT','MARKETPLACE_ORDER')")
        if not _enum_exists(bind, "razorpaypaymentstatus"):
            op.execute("CREATE TYPE razorpaypaymentstatus AS ENUM ('CREATED','COMPLETED','FAILED')")

    purpose_type = (
        sa.Enum("FARMER_PAYOUT", "MARKETPLACE_ORDER",
                name="razorpaypaymentpurpose", create_type=False)
        if is_pg else sa.String(50)
    )
    status_type = (
        sa.Enum("CREATED", "COMPLETED", "FAILED",
                name="razorpaypaymentstatus", create_type=False)
        if is_pg else sa.String(20)
    )

    op.execute("""
        CREATE TABLE IF NOT EXISTS razorpay_payments (
            id                  SERIAL PRIMARY KEY,
            purpose             VARCHAR(50)  NOT NULL,
            reference_id        INTEGER      NOT NULL,
            razorpay_order_id   VARCHAR(100) NOT NULL UNIQUE,
            razorpay_payment_id VARCHAR(100),
            razorpay_signature  VARCHAR(500),
            signature_verified  BOOLEAN      NOT NULL DEFAULT FALSE,
            amount_paise        INTEGER      NOT NULL,
            currency            VARCHAR(10)  NOT NULL DEFAULT 'INR',
            status              VARCHAR(20)  NOT NULL DEFAULT 'CREATED',
            failure_reason      VARCHAR(500),
            initiated_by        INTEGER      NOT NULL REFERENCES users(id),
            created_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
            completed_at        TIMESTAMPTZ
        )
    """ if is_pg else """
        CREATE TABLE IF NOT EXISTS razorpay_payments (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            purpose             VARCHAR(50)  NOT NULL,
            reference_id        INTEGER      NOT NULL,
            razorpay_order_id   VARCHAR(100) NOT NULL UNIQUE,
            razorpay_payment_id VARCHAR(100),
            razorpay_signature  VARCHAR(500),
            signature_verified  BOOLEAN      NOT NULL DEFAULT 0,
            amount_paise        INTEGER      NOT NULL,
            currency            VARCHAR(10)  NOT NULL DEFAULT 'INR',
            status              VARCHAR(20)  NOT NULL DEFAULT 'CREATED',
            failure_reason      VARCHAR(500),
            initiated_by        INTEGER      NOT NULL REFERENCES users(id),
            created_at          DATETIME     NOT NULL,
            completed_at        DATETIME
        )
    """)

    # Indexes (idempotent via IF NOT EXISTS — PostgreSQL 9.5+; SQLite always)
    if is_pg:
        op.execute("CREATE INDEX IF NOT EXISTS ix_razorpay_payments_reference_id ON razorpay_payments(reference_id)")
        op.execute("CREATE INDEX IF NOT EXISTS ix_razorpay_payments_razorpay_order_id ON razorpay_payments(razorpay_order_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS razorpay_payments")
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP TYPE IF EXISTS razorpaypaymentpurpose")
        op.execute("DROP TYPE IF EXISTS razorpaypaymentstatus")
