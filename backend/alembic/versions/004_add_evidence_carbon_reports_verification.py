"""Add evidence_files, carbon_reports, verification_requests tables

Revision ID: 004
Revises: 003
Create Date: 2026-05-31

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── evidence_files ────────────────────────────────────────────────────
    op.create_table(
        "evidence_files",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("farm_id", sa.Integer(), nullable=False),
        sa.Column("crop_cycle_id", sa.Integer(), nullable=False),
        sa.Column("uploaded_by", sa.Integer(), nullable=False),
        sa.Column("file_url", sa.String(length=1024), nullable=False),
        sa.Column("file_type", sa.String(length=50), nullable=False),
        sa.Column("description", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["farm_id"], ["farms.id"]),
        sa.ForeignKeyConstraint(["crop_cycle_id"], ["crop_cycles.id"]),
        sa.ForeignKeyConstraint(["uploaded_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_evidence_files_id"), "evidence_files", ["id"], unique=False)
    op.create_index(op.f("ix_evidence_files_farm_id"), "evidence_files", ["farm_id"], unique=False)
    op.create_index(op.f("ix_evidence_files_crop_cycle_id"), "evidence_files", ["crop_cycle_id"], unique=False)
    op.create_index(op.f("ix_evidence_files_uploaded_by"), "evidence_files", ["uploaded_by"], unique=False)

    # ── carbon_reports ────────────────────────────────────────────────────
    op.create_table(
        "carbon_reports",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("farm_id", sa.Integer(), nullable=False),
        sa.Column("crop_cycle_id", sa.Integer(), nullable=False),
        sa.Column("baseline_methane_kg", sa.Float(), nullable=False),
        sa.Column("current_methane_kg", sa.Float(), nullable=False),
        sa.Column("methane_reduction_kg", sa.Float(), nullable=False),
        sa.Column("co2e_reduction_tonnes", sa.Float(), nullable=False),
        sa.Column("estimated_credits", sa.Integer(), nullable=False),
        sa.Column("report_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "status",
            sa.Enum("DRAFT", "SUBMITTED", "VERIFIED", "REJECTED", name="reportstatus"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["farm_id"], ["farms.id"]),
        sa.ForeignKeyConstraint(["crop_cycle_id"], ["crop_cycles.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_carbon_reports_id"), "carbon_reports", ["id"], unique=False)
    op.create_index(op.f("ix_carbon_reports_farm_id"), "carbon_reports", ["farm_id"], unique=False)
    op.create_index(op.f("ix_carbon_reports_crop_cycle_id"), "carbon_reports", ["crop_cycle_id"], unique=False)

    # ── verification_requests ─────────────────────────────────────────────
    op.create_table(
        "verification_requests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("carbon_report_id", sa.Integer(), nullable=False),
        sa.Column("verifier_id", sa.Integer(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("PENDING", "APPROVED", "REJECTED", "MANUAL_REVIEW", name="verificationstatus"),
            nullable=False,
        ),
        sa.Column("remarks", sa.String(length=1024), nullable=True),
        sa.Column("risk_score", sa.Float(), nullable=False),
        sa.Column(
            "risk_level",
            sa.Enum("LOW", "MEDIUM", "HIGH", name="risklevel"),
            nullable=False,
        ),
        sa.Column(
            "recommendation",
            sa.Enum("APPROVE", "MANUAL_REVIEW", "REJECT", name="recommendation"),
            nullable=False,
        ),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["carbon_report_id"], ["carbon_reports.id"]),
        sa.ForeignKeyConstraint(["verifier_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_verification_requests_id"), "verification_requests", ["id"], unique=False)
    op.create_index(op.f("ix_verification_requests_carbon_report_id"), "verification_requests", ["carbon_report_id"], unique=False)
    op.create_index(op.f("ix_verification_requests_verifier_id"), "verification_requests", ["verifier_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_verification_requests_verifier_id"), table_name="verification_requests")
    op.drop_index(op.f("ix_verification_requests_carbon_report_id"), table_name="verification_requests")
    op.drop_index(op.f("ix_verification_requests_id"), table_name="verification_requests")
    op.drop_table("verification_requests")
    op.execute("DROP TYPE IF EXISTS verificationstatus")
    op.execute("DROP TYPE IF EXISTS risklevel")
    op.execute("DROP TYPE IF EXISTS recommendation")

    op.drop_index(op.f("ix_carbon_reports_crop_cycle_id"), table_name="carbon_reports")
    op.drop_index(op.f("ix_carbon_reports_farm_id"), table_name="carbon_reports")
    op.drop_index(op.f("ix_carbon_reports_id"), table_name="carbon_reports")
    op.drop_table("carbon_reports")
    op.execute("DROP TYPE IF EXISTS reportstatus")

    op.drop_index(op.f("ix_evidence_files_uploaded_by"), table_name="evidence_files")
    op.drop_index(op.f("ix_evidence_files_crop_cycle_id"), table_name="evidence_files")
    op.drop_index(op.f("ix_evidence_files_farm_id"), table_name="evidence_files")
    op.drop_index(op.f("ix_evidence_files_id"), table_name="evidence_files")
    op.drop_table("evidence_files")
