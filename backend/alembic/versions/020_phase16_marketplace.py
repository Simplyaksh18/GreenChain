"""Phase 16 — Marketplace & Registry tables.

Creates:
  - marketplace_listings
  - marketplace_orders
  - retirement_certificates
  - listing_status enum (PostgreSQL)
  - order_status enum (PostgreSQL)

Idempotent: uses IF NOT EXISTS for tables and checks for enum existence.

Revision ID: 020_phase16_marketplace
Revises: 019_google_auth
Create Date: 2026-06-10
"""
from __future__ import annotations
from typing import Union

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision: str = "020_phase16_marketplace"
down_revision: Union[str, None] = "019_google_auth"
branch_labels = None
depends_on = None


def _enum_exists(connection, name: str) -> bool:
    result = connection.execute(
        sa.text("SELECT 1 FROM pg_type WHERE typname = :name"),
        {"name": name},
    )
    return result.fetchone() is not None


def upgrade() -> None:
    conn = op.get_bind()

    # ── Create enums only if they don't exist ─────────────────────────────────

    if not _enum_exists(conn, "listingstatus"):
        conn.execute(sa.text(
            "CREATE TYPE listingstatus AS ENUM "
            "('ACTIVE', 'PAUSED', 'SOLD_OUT', 'CANCELLED')"
        ))

    if not _enum_exists(conn, "orderstatus"):
        conn.execute(sa.text(
            "CREATE TYPE orderstatus AS ENUM "
            "('INTERESTED', 'APPROVED', 'REJECTED', 'PAID', 'RETIRED')"
        ))

    # ── marketplace_listings ──────────────────────────────────────────────────

    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS marketplace_listings (
            id                        SERIAL PRIMARY KEY,
            farmer_credit_balance_id  INTEGER NOT NULL
                REFERENCES farmer_credit_balances(id),
            fpo_id                    INTEGER NOT NULL
                REFERENCES fpo_profiles(id),
            farmer_id                 INTEGER
                REFERENCES users(id),
            carbon_token_id           INTEGER NOT NULL
                REFERENCES carbon_tokens(id),
            credits_listed            INTEGER NOT NULL,
            credits_available         INTEGER NOT NULL,
            price_per_credit          INTEGER NOT NULL,
            currency                  VARCHAR(10) NOT NULL DEFAULT 'INR',
            listing_status            listingstatus NOT NULL DEFAULT 'ACTIVE',
            created_at                TIMESTAMP WITH TIME ZONE
                NOT NULL DEFAULT NOW(),
            updated_at                TIMESTAMP WITH TIME ZONE
        )
    """))

    # ── marketplace_orders ────────────────────────────────────────────────────

    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS marketplace_orders (
            id                  SERIAL PRIMARY KEY,
            listing_id          INTEGER NOT NULL
                REFERENCES marketplace_listings(id),
            buyer_name          VARCHAR(255) NOT NULL,
            buyer_email         VARCHAR(255),
            buyer_organization  VARCHAR(255),
            credits_requested   INTEGER NOT NULL,
            quoted_amount       BIGINT NOT NULL,
            order_status        orderstatus NOT NULL DEFAULT 'INTERESTED',
            created_at          TIMESTAMP WITH TIME ZONE
                NOT NULL DEFAULT NOW()
        )
    """))

    # ── retirement_certificates ───────────────────────────────────────────────

    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS retirement_certificates (
            id                  SERIAL PRIMARY KEY,
            order_id            INTEGER NOT NULL UNIQUE
                REFERENCES marketplace_orders(id),
            token_id            INTEGER NOT NULL
                REFERENCES carbon_tokens(id),
            buyer_name          VARCHAR(255) NOT NULL,
            credits_retired     INTEGER NOT NULL,
            retirement_reason   TEXT,
            certificate_hash    VARCHAR(64) NOT NULL,
            created_at          TIMESTAMP WITH TIME ZONE
                NOT NULL DEFAULT NOW()
        )
    """))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DROP TABLE IF EXISTS retirement_certificates CASCADE"))
    conn.execute(sa.text("DROP TABLE IF EXISTS marketplace_orders CASCADE"))
    conn.execute(sa.text("DROP TABLE IF EXISTS marketplace_listings CASCADE"))
    conn.execute(sa.text("DROP TYPE IF EXISTS orderstatus"))
    conn.execute(sa.text("DROP TYPE IF EXISTS listingstatus"))
