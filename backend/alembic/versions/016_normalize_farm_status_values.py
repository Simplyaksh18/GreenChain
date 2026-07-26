"""016_normalize_farm_status_values

Data migration — idempotent normalizer for farm_status column.

Problem
-------
Some rows may contain:
  - Lowercase variants:  'pending', 'approved', 'draft', 'suspended', 'archived'
  - Alternate spelling:  'pending_approval', 'PENDING'
  - NULL values
  - Valid values but inconsistent with is_approved boolean

This migration:
  1. Maps all known variant spellings → canonical uppercase enum values
  2. Repairs NULL farm_status  (is_approved=TRUE → APPROVED, else PENDING_APPROVAL)
  3. Repairs is_approved/farm_status mismatch
     (is_approved=TRUE but farm_status != 'APPROVED' → APPROVED)
  4. Ensures no row has a value outside the allowed set

Allowed canonical values: DRAFT, PENDING_APPROVAL, APPROVED, SUSPENDED, ARCHIVED

Revision ID: 016_normalize_farm_status_values
Revises: 015_phase11_farm_crop_lifecycle
Create Date: 2026-06-05
"""
from alembic import op
import sqlalchemy as sa

revision = "016_normalize_farm_status_values"
down_revision = "015_phase11_farm_crop_lifecycle"
branch_labels = None
depends_on = None


# Mapping: any raw DB string → canonical enum value
_NORMALIZATION_MAP = {
    # NULL handled separately
    "pending":            "PENDING_APPROVAL",
    "PENDING":            "PENDING_APPROVAL",
    "pending_approval":   "PENDING_APPROVAL",
    # Lowercase of canonical values
    "draft":              "DRAFT",
    "approved":           "APPROVED",
    "suspended":          "SUSPENDED",
    "archived":           "ARCHIVED",
}

_ALLOWED = {"DRAFT", "PENDING_APPROVAL", "APPROVED", "SUSPENDED", "ARCHIVED"}


def upgrade():
    bind = op.get_bind()

    # ── Step 1: normalize known variant spellings ──────────────────────────────
    for bad_value, good_value in _NORMALIZATION_MAP.items():
        bind.execute(sa.text(
            "UPDATE farms SET farm_status = :good WHERE farm_status = :bad"
        ), {"good": good_value, "bad": bad_value})

    # ── Step 2: repair NULL farm_status ───────────────────────────────────────
    bind.execute(sa.text(
        "UPDATE farms SET farm_status = 'APPROVED' "
        "WHERE farm_status IS NULL AND is_approved = TRUE"
    ))
    bind.execute(sa.text(
        "UPDATE farms SET farm_status = 'PENDING_APPROVAL' "
        "WHERE farm_status IS NULL AND is_approved = FALSE"
    ))

    # ── Step 3: repair is_approved / farm_status mismatch ─────────────────────
    # Farms that are is_approved=TRUE but not yet marked APPROVED in farm_status
    # (e.g. still in PENDING_APPROVAL because a previous migration missed them)
    bind.execute(sa.text(
        "UPDATE farms SET farm_status = 'APPROVED' "
        "WHERE is_approved = TRUE AND farm_status != 'APPROVED'"
    ))

    # ── Step 4: catch-all — anything still unknown → DRAFT ────────────────────
    #    Build an SQL IN clause for the allowed set
    allowed_sql = ", ".join(f"'{v}'" for v in _ALLOWED)
    bind.execute(sa.text(
        f"UPDATE farms SET farm_status = 'DRAFT' "
        f"WHERE farm_status NOT IN ({allowed_sql})"
    ))


def downgrade():
    # Data migrations are not reversible in a meaningful way.
    pass
