"""Add wallet_address to users table

Revision ID: 006
Revises: 005
Create Date: 2026-06-01

Adds an optional Ethereum/Polygon wallet address field to users.
Nullable — not required for existing users.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "wallet_address",
            sa.String(length=42),
            nullable=True,
            comment="Optional Ethereum/Polygon wallet address (0x-prefixed, 42 chars)",
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "wallet_address")
