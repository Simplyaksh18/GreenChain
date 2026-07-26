"""Phase 15 — Google OAuth user fields (additive only)

Revision ID: 019_google_auth
Revises: 018_ev_upload
Create Date: 2026-06-07

Adds to users table:
  auth_provider     VARCHAR(10)   NOT NULL DEFAULT 'PASSWORD'
                    Values: PASSWORD | GOOGLE
  google_sub        VARCHAR(200)  nullable  — Google user ID (sub)
  profile_photo_url VARCHAR(500)  nullable  — Google profile picture URL

All columns are nullable-safe for existing rows (auth_provider gets 'PASSWORD').
Does NOT alter password_hash or any existing column.
"""
from __future__ import annotations
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.engine.reflection import Inspector

revision: str = "019_google_auth"
down_revision: Union[str, None] = "018_ev_upload"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _cols(table: str) -> set[str]:
    return {c["name"] for c in Inspector.from_engine(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    cols = _cols("users")

    if "auth_provider" not in cols:
        op.add_column(
            "users",
            sa.Column(
                "auth_provider",
                sa.String(10),
                nullable=False,
                server_default="PASSWORD",
            ),
        )

    if "google_sub" not in cols:
        op.add_column(
            "users",
            sa.Column("google_sub", sa.String(200), nullable=True),
        )

    if "profile_photo_url" not in cols:
        op.add_column(
            "users",
            sa.Column("profile_photo_url", sa.String(500), nullable=True),
        )


def downgrade() -> None:
    cols = _cols("users")
    for col in ("profile_photo_url", "google_sub", "auth_provider"):
        if col in cols:
            op.drop_column("users", col)
