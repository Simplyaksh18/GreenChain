"""Phase 22B — marketplace payment tracking fields.

Adds four columns to `marketplace_orders` to support the manual/test payment
flow (RazorpayX remains for farmer payouts only; this is not real buyer
checkout):

  paid_at            DATETIME(TZ)  NULL
  paid_by_user_id    INTEGER FK users(id)  NULL
  payment_reference  VARCHAR(255)  NULL
  payment_method     VARCHAR(50)   NULL  (recorded as 'MANUAL_TEST')

No column is removed or replaced. Existing rows keep their current values.
Any row already in PAID or RETIRED status is backfilled with
paid_at = created_at and payment_method = 'MANUAL_TEST' so the historical
record is consistent with the new schema.

Reservation quantity is intentionally NOT stored on a new column — the
existing MarketplaceOrder.credits_requested combined with order.status
∈ {APPROVED, PAID} is the reservation source of truth.

Revision ID: 022_phase22b_marketplace_payment_fields
Revises: 021_razorpay_payments
Create Date: 2026-07-05
"""
from __future__ import annotations

from typing import Union

from alembic import op
import sqlalchemy as sa


revision: str = "022_phase22b_marketplace_payment_fields"
down_revision: Union[str, None] = "021_razorpay_payments"
branch_labels = None
depends_on = None


def _has_column(connection, table: str, column: str) -> bool:
    """Dialect-agnostic column presence check (Postgres + SQLite)."""
    inspector = sa.inspect(connection)
    return column in {c["name"] for c in inspector.get_columns(table)}


def upgrade() -> None:
    conn = op.get_bind()

    # buyer_user_id: track the authenticated user who submitted the order,
    # so /marketplace/my-orders and buyer-scoped certificate access work.
    if not _has_column(conn, "marketplace_orders", "buyer_user_id"):
        op.add_column(
            "marketplace_orders",
            sa.Column("buyer_user_id", sa.Integer(), nullable=True),
        )
        with op.batch_alter_table("marketplace_orders") as batch:
            batch.create_index(
                "ix_marketplace_orders_buyer_user_id",
                ["buyer_user_id"],
            )
            batch.create_foreign_key(
                "fk_marketplace_orders_buyer_user_id_users",
                "users",
                ["buyer_user_id"],
                ["id"],
                ondelete="SET NULL",
            )

    # Add columns only if they don't already exist (safe re-runs).
    if not _has_column(conn, "marketplace_orders", "paid_at"):
        op.add_column(
            "marketplace_orders",
            sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        )
    if not _has_column(conn, "marketplace_orders", "paid_by_user_id"):
        op.add_column(
            "marketplace_orders",
            sa.Column("paid_by_user_id", sa.Integer(), nullable=True),
        )
        # Foreign key added separately so SQLite's ALTER limitations don't bite.
        with op.batch_alter_table("marketplace_orders") as batch:
            batch.create_foreign_key(
                "fk_marketplace_orders_paid_by_user_id_users",
                "users",
                ["paid_by_user_id"],
                ["id"],
                ondelete="SET NULL",
            )
    if not _has_column(conn, "marketplace_orders", "payment_reference"):
        op.add_column(
            "marketplace_orders",
            sa.Column("payment_reference", sa.String(length=255), nullable=True),
        )
    if not _has_column(conn, "marketplace_orders", "payment_method"):
        op.add_column(
            "marketplace_orders",
            sa.Column("payment_method", sa.String(length=50), nullable=True),
        )

    # Backfill: rows already in PAID or RETIRED get a synthetic paid_at so
    # reports/audits don't show NULL for historically completed payments.
    conn.execute(
        sa.text(
            "UPDATE marketplace_orders "
            "SET paid_at = created_at, "
            "    payment_method = COALESCE(payment_method, 'MANUAL_TEST') "
            "WHERE order_status IN ('PAID', 'RETIRED') AND paid_at IS NULL"
        )
    )


def downgrade() -> None:
    conn = op.get_bind()

    # Drop FK first if it exists (Postgres will complain otherwise).
    if _has_column(conn, "marketplace_orders", "paid_by_user_id"):
        try:
            op.drop_constraint(
                "fk_marketplace_orders_paid_by_user_id_users",
                "marketplace_orders",
                type_="foreignkey",
            )
        except Exception:
            # SQLite doesn't support named FK drop; batch mode handles the column.
            pass

    for col in (
        "payment_method", "payment_reference", "paid_by_user_id", "paid_at",
        "buyer_user_id",
    ):
        if _has_column(conn, "marketplace_orders", col):
            with op.batch_alter_table("marketplace_orders") as batch:
                batch.drop_column(col)
