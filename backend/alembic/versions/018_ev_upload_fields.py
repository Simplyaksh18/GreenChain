"""Phase 14 — Evidence upload fields (additive only)

Revision ID: 018_ev_upload
Revises: 017_ev_audit
Create Date: 2026-06-07

Adds to evidence_files:
  evidence_type    VARCHAR(30)   default 'OTHER'
  file_name        VARCHAR(500)  nullable
  file_mime_type   VARCHAR(100)  nullable
  file_size        INTEGER       nullable (bytes)
  storage_path     VARCHAR(1024) nullable

Also drops NOT NULL constraint from crop_cycle_id so farm-level
evidence (not tied to a specific cycle) is supported.

Idempotent — checks column existence before every add.
Does NOT touch any unrelated table.
"""
from __future__ import annotations
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.engine.reflection import Inspector

revision: str = "018_ev_upload"
down_revision: Union[str, None] = "017_ev_audit"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _cols(table: str) -> set[str]:
    bind = op.get_bind()
    return {c["name"] for c in Inspector.from_engine(bind).get_columns(table)}


def upgrade() -> None:
    cols = _cols("evidence_files")

    if "evidence_type" not in cols:
        op.add_column(
            "evidence_files",
            sa.Column("evidence_type", sa.String(30), nullable=True, server_default="OTHER"),
        )

    if "file_name" not in cols:
        op.add_column(
            "evidence_files",
            sa.Column("file_name", sa.String(500), nullable=True),
        )

    if "file_mime_type" not in cols:
        op.add_column(
            "evidence_files",
            sa.Column("file_mime_type", sa.String(100), nullable=True),
        )

    if "file_size" not in cols:
        op.add_column(
            "evidence_files",
            sa.Column("file_size", sa.Integer(), nullable=True),
        )

    if "storage_path" not in cols:
        op.add_column(
            "evidence_files",
            sa.Column("storage_path", sa.String(1024), nullable=True),
        )

    # Make crop_cycle_id nullable — farm-level evidence may not have a cycle.
    # PostgreSQL: ALTER COLUMN ... DROP NOT NULL
    # SQLite:     not supported — test DB is created from model directly.
    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        op.alter_column(
            "evidence_files",
            "crop_cycle_id",
            existing_type=sa.Integer(),
            nullable=True,
        )


def downgrade() -> None:
    cols = _cols("evidence_files")

    for col in ("storage_path", "file_size", "file_mime_type", "file_name", "evidence_type"):
        if col in cols:
            op.drop_column("evidence_files", col)

    # Restore NOT NULL on crop_cycle_id (only if no nulls exist)
    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        op.alter_column(
            "evidence_files",
            "crop_cycle_id",
            existing_type=sa.Integer(),
            nullable=False,
        )
