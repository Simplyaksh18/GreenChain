"""Add blockchain_transactions and carbon_tokens tables

Revision ID: 005
Revises: 004
Create Date: 2026-06-01

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── blockchain_transactions ───────────────────────────────────────────
    op.create_table(
        "blockchain_transactions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("carbon_report_id", sa.Integer(), nullable=False),
        sa.Column("tx_hash", sa.String(length=66), nullable=False),
        sa.Column(
            "blockchain_network",
            sa.String(length=64),
            nullable=False,
            server_default="MOCK_POLYGON_AMOY",
        ),
        sa.Column(
            "contract_address",
            sa.String(length=64),
            nullable=False,
            server_default="0xMockGreenChainContract000000000000000000",
        ),
        sa.Column(
            "action_type",
            sa.Enum("REPORT_HASH", "TOKEN_MINT", "TOKEN_RETIRE", "TOKEN_SUSPEND",
                    name="actiontype"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["carbon_report_id"], ["carbon_reports.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tx_hash"),
    )
    op.create_index(op.f("ix_blockchain_transactions_id"),
                    "blockchain_transactions", ["id"], unique=False)
    op.create_index(op.f("ix_blockchain_transactions_carbon_report_id"),
                    "blockchain_transactions", ["carbon_report_id"], unique=False)

    # ── carbon_tokens ─────────────────────────────────────────────────────
    op.create_table(
        "carbon_tokens",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("carbon_report_id", sa.Integer(), nullable=False),
        sa.Column("farmer_id", sa.Integer(), nullable=False),
        sa.Column("token_id", sa.String(length=64), nullable=False),
        sa.Column("token_standard", sa.String(length=32), nullable=False,
                  server_default="ERC1155_MOCK"),
        sa.Column("credit_amount", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("MINTED", "RETIRED", "SUSPENDED", name="tokenstatus"),
            nullable=False,
        ),
        sa.Column("minted_tx_hash", sa.String(length=66), nullable=True),
        sa.Column("minted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["carbon_report_id"], ["carbon_reports.id"]),
        sa.ForeignKeyConstraint(["farmer_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("carbon_report_id"),
        sa.UniqueConstraint("token_id"),
    )
    op.create_index(op.f("ix_carbon_tokens_id"),
                    "carbon_tokens", ["id"], unique=False)
    op.create_index(op.f("ix_carbon_tokens_carbon_report_id"),
                    "carbon_tokens", ["carbon_report_id"], unique=False)
    op.create_index(op.f("ix_carbon_tokens_farmer_id"),
                    "carbon_tokens", ["farmer_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_carbon_tokens_farmer_id"), table_name="carbon_tokens")
    op.drop_index(op.f("ix_carbon_tokens_carbon_report_id"), table_name="carbon_tokens")
    op.drop_index(op.f("ix_carbon_tokens_id"), table_name="carbon_tokens")
    op.drop_table("carbon_tokens")
    op.execute("DROP TYPE IF EXISTS tokenstatus")

    op.drop_index(op.f("ix_blockchain_transactions_carbon_report_id"),
                  table_name="blockchain_transactions")
    op.drop_index(op.f("ix_blockchain_transactions_id"),
                  table_name="blockchain_transactions")
    op.drop_table("blockchain_transactions")
    op.execute("DROP TYPE IF EXISTS actiontype")
