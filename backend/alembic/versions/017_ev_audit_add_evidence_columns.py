"""Phase 13 — Evidence audit columns (additive only)

Revision ID: 017_ev_audit
Revises: 2b2eecf4af1a
Create Date: 2026-06-07

ADDITIVE ONLY — adds three nullable columns to evidence_files:
  carbon_report_id  INTEGER  FK → carbon_reports.id  (nullable)
  file_hash         VARCHAR(128)  hex digest          (nullable)
  hash_algorithm    VARCHAR(20)   default 'SHA256'    (nullable)

Idempotent: checks column existence before adding each column/index.
Does NOT alter any existing column, enum, constraint, or table.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.engine.reflection import Inspector

# ---------------------------------------------------------------------------
# Revision identifiers — MUST stay ≤ 32 characters (alembic_version VARCHAR(32))
# ---------------------------------------------------------------------------
revision: str = "017_ev_audit"
down_revision: Union[str, None] = "2b2eecf4af1a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _existing_columns(table: str) -> set[str]:
    bind = op.get_bind()
    inspector = Inspector.from_engine(bind)
    return {col["name"] for col in inspector.get_columns(table)}


def _existing_indexes(table: str) -> set[str]:
    bind = op.get_bind()
    inspector = Inspector.from_engine(bind)
    return {idx["name"] for idx in inspector.get_indexes(table)}


def upgrade() -> None:
    cols = _existing_columns("evidence_files")
    idxs = _existing_indexes("evidence_files")

    # -- carbon_report_id: FK to carbon_reports, nullable ----------------
    if "carbon_report_id" not in cols:
        op.add_column(
            "evidence_files",
            sa.Column(
                "carbon_report_id",
                sa.Integer(),
                sa.ForeignKey("carbon_reports.id", ondelete="SET NULL"),
                nullable=True,
            ),
        )

    if "ix_evidence_files_carbon_report_id" not in idxs and "carbon_report_id" in (
        _existing_columns("evidence_files")
    ):
        op.create_index(
            "ix_evidence_files_carbon_report_id",
            "evidence_files",
            ["carbon_report_id"],
            unique=False,
        )

    # -- file_hash: hex digest, VARCHAR(128) to accommodate future algos --
    if "file_hash" not in cols:
        op.add_column(
            "evidence_files",
            sa.Column("file_hash", sa.String(128), nullable=True),
        )

    # -- hash_algorithm: VARCHAR(20), server default 'SHA256' -------------
    if "hash_algorithm" not in cols:
        op.add_column(
            "evidence_files",
            sa.Column(
                "hash_algorithm",
                sa.String(20),
                nullable=True,
                server_default="SHA256",
            ),
        )


def downgrade() -> None:
    cols = _existing_columns("evidence_files")
    idxs = _existing_indexes("evidence_files")

    if "hash_algorithm" in cols:
        op.drop_column("evidence_files", "hash_algorithm")

    if "file_hash" in cols:
        op.drop_column("evidence_files", "file_hash")

    if "carbon_report_id" in cols:
        if "ix_evidence_files_carbon_report_id" in idxs:
            op.drop_index(
                "ix_evidence_files_carbon_report_id",
                table_name="evidence_files",
            )
        op.drop_column("evidence_files", "carbon_report_id")
