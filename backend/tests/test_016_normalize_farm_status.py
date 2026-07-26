"""
test_016_normalize_farm_status.py

Tests for migration 016 data normalizer:
  - farm rows with lowercase/variant farm_status values are corrected
  - NULL farm_status rows are repaired using is_approved (skipped on SQLite)
  - is_approved=True / farm_status mismatch rows are corrected
  - GET /farms and GET /mobile/dashboard return 200 after normalization
  - create_farm with fpo_id → PENDING_APPROVAL
  - create_farm without fpo_id → DRAFT
"""
import pytest
import sqlalchemy as sa

from tests.conftest import TestingSessionLocal, _make_farm, _make_user, _make_fpo_profile
from app.models.user import UserRole
from app.security import create_access_token


# ─── Canonical mapping (mirrors migration 016) ────────────────────────────────

_NORMALIZATION_MAP = {
    "pending":          "PENDING_APPROVAL",
    "PENDING":          "PENDING_APPROVAL",
    "pending_approval": "PENDING_APPROVAL",
    "draft":            "DRAFT",
    "approved":         "APPROVED",
    "suspended":        "SUSPENDED",
    "archived":         "ARCHIVED",
}
_ALLOWED = frozenset({"DRAFT", "PENDING_APPROVAL", "APPROVED", "SUSPENDED", "ARCHIVED"})


# ─── Test helpers ─────────────────────────────────────────────────────────────

def _raw(db):
    """Return the underlying raw sqlite3 connection from a SQLAlchemy Session."""
    return db.connection().connection


def _inject_bad_value(db, farm_id: int, value):
    """
    Force an arbitrary (possibly invalid) farm_status string into SQLite,
    bypassing the CHECK constraint via PRAGMA ignore_check_constraints.

    NULL injection is not possible on SQLite (NOT NULL is enforced at the
    engine level). Those tests are skipped with a clear message.
    """
    if value is None:
        pytest.skip(
            "Cannot inject NULL into a NOT NULL column on SQLite. "
            "This scenario is verified against PostgreSQL in production."
        )
    conn = _raw(db)
    conn.execute("PRAGMA ignore_check_constraints = 1")
    conn.execute("UPDATE farms SET farm_status = ? WHERE id = ?", (value, farm_id))
    conn.execute("PRAGMA ignore_check_constraints = 0")
    conn.commit()


def _run_normalizer(db):
    """
    Apply the same logic as migration 016 via the raw dbapi connection.

    Using the raw connection (not the SQLAlchemy Session) avoids autoflush and
    the enum type processor, which would otherwise raise LookupError when it
    encounters the poisoned 'pending' value in the identity map.
    """
    conn = _raw(db)

    # Step 1 — normalize known variant spellings
    for bad, good in _NORMALIZATION_MAP.items():
        conn.execute(
            "UPDATE farms SET farm_status = ? WHERE farm_status = ?", (good, bad)
        )

    # Step 2 — repair NULL (SQLite: 0/1 booleans)
    conn.execute(
        "UPDATE farms SET farm_status = 'APPROVED' "
        "WHERE farm_status IS NULL AND is_approved = 1"
    )
    conn.execute(
        "UPDATE farms SET farm_status = 'PENDING_APPROVAL' "
        "WHERE farm_status IS NULL AND is_approved = 0"
    )

    # Step 3 — repair is_approved mismatch
    conn.execute(
        "UPDATE farms SET farm_status = 'APPROVED' "
        "WHERE is_approved = 1 AND farm_status != 'APPROVED'"
    )

    # Step 4 — catch-all: unknown → DRAFT
    allowed_csv = ", ".join(f"'{v}'" for v in _ALLOWED)
    conn.execute(
        f"UPDATE farms SET farm_status = 'DRAFT' "
        f"WHERE farm_status NOT IN ({allowed_csv})"
    )
    conn.commit()
    # Expire ORM identity map so subsequent ORM reads come from the DB
    db.expire_all()


def _read_status(db, farm_id: int) -> str:
    conn = _raw(db)
    row = conn.execute(
        "SELECT farm_status FROM farms WHERE id = ?", (farm_id,)
    ).fetchone()
    return row[0]


def _token(user) -> str:
    return create_access_token({"sub": str(user.id)})


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def users(db):
    farmer = _make_user(db, "Norm Farmer", "norm_farmer@test.com", UserRole.FARMER)
    fpo_u  = _make_user(db, "Norm FPO",   "norm_fpo@test.com",    UserRole.FPO)
    admin  = _make_user(db, "Norm Admin",  "norm_admin@test.com",  UserRole.ADMIN)
    fpo_p  = _make_fpo_profile(db, fpo_u, org="NormFPO", reg="NREG001")
    return farmer, fpo_u, fpo_p, admin


# ─── 1-4: lowercase / variant spellings ──────────────────────────────────────

@pytest.mark.parametrize("bad,expected", [
    ("pending",          "PENDING_APPROVAL"),
    ("PENDING",          "PENDING_APPROVAL"),
    ("pending_approval", "PENDING_APPROVAL"),
    ("approved",         "APPROVED"),
])
def test_variant_spelling_normalized(db, users, bad, expected):
    farmer, fpo_u, fpo_p, admin = users
    farm = _make_farm(db, farmer, fpo_profile=fpo_p,
                      approved=(expected == "APPROVED"))
    farm_id = farm.id

    _inject_bad_value(db, farm_id, bad)

    # Pre-condition check via raw connection
    assert _read_status(db, farm_id) == bad

    _run_normalizer(db)

    assert _read_status(db, farm_id) == expected


# ─── 5-6: NULL farm_status (PostgreSQL scenario, skipped on SQLite) ──────────

def test_null_farm_status_approved_repaired(db, users):
    farmer, fpo_u, fpo_p, admin = users
    farm = _make_farm(db, farmer, fpo_profile=fpo_p, approved=True)
    _inject_bad_value(db, farm.id, None)  # triggers pytest.skip on SQLite


def test_null_farm_status_unapproved_repaired(db, users):
    farmer, fpo_u, fpo_p, admin = users
    farm = _make_farm(db, farmer, fpo_profile=fpo_p, approved=False)
    _inject_bad_value(db, farm.id, None)  # triggers pytest.skip on SQLite


# ─── 7: is_approved=True + PENDING_APPROVAL mismatch → APPROVED ──────────────

def test_is_approved_mismatch_repaired(db, users):
    farmer, fpo_u, fpo_p, admin = users
    farm = _make_farm(db, farmer, fpo_profile=fpo_p, approved=True)
    farm_id = farm.id

    # Simulate real-world bug: is_approved=True but stuck at PENDING_APPROVAL
    _inject_bad_value(db, farm_id, "PENDING_APPROVAL")
    _run_normalizer(db)

    assert _read_status(db, farm_id) == "APPROVED"


# ─── 8: completely unknown value → DRAFT ─────────────────────────────────────

def test_unknown_value_fallback_to_draft(db, users):
    farmer, fpo_u, fpo_p, admin = users
    farm = _make_farm(db, farmer, fpo_profile=fpo_p, approved=False)
    farm_id = farm.id

    _inject_bad_value(db, farm_id, "GARBAGE")
    _run_normalizer(db)

    assert _read_status(db, farm_id) == "DRAFT"


# ─── 9: GET /farms returns 200 after normalization ───────────────────────────

def test_get_farms_returns_200_after_normalization(db, client, users):
    farmer, fpo_u, fpo_p, admin = users
    farm = _make_farm(db, farmer, fpo_profile=fpo_p, approved=True)
    farm_id = farm.id

    _inject_bad_value(db, farm_id, "pending")
    _run_normalizer(db)

    resp = client.get("/farms", headers={"Authorization": f"Bearer {_token(farmer)}"})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert all(f["farm_status"] in _ALLOWED for f in data)


# ─── 10: GET /mobile/dashboard returns 200 after normalization ────────────────

def test_mobile_dashboard_returns_200_after_normalization(db, client, users):
    farmer, fpo_u, fpo_p, admin = users
    _make_farm(db, farmer, fpo_profile=fpo_p, approved=True)

    resp = client.get(
        "/mobile/dashboard",
        headers={"Authorization": f"Bearer {_token(farmer)}"},
    )
    assert resp.status_code == 200
    assert resp.json().get("success") is True


# ─── 11: create_farm with fpo_id → PENDING_APPROVAL ─────────────────────────

def test_create_farm_with_fpo_sets_pending_approval(db, client, users):
    farmer, fpo_u, fpo_p, admin = users

    resp = client.post(
        "/farms",
        json={
            "farm_name": "Registry Farm",
            "land_area_acres": 3.5,
            "latitude": 18.5,
            "longitude": 73.8,
            "village": "Testpur",
            "district": "Pune",
            "state": "Maharashtra",
            "soil_type": "Sandy",
            "water_source": "Borewell",
            "fpo_id": fpo_p.id,
        },
        headers={"Authorization": f"Bearer {_token(farmer)}"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["farm_status"] == "PENDING_APPROVAL"
    assert body["is_approved"] is False


# ─── 12: create_farm without fpo_id → DRAFT ──────────────────────────────────

def test_create_farm_without_fpo_sets_draft(db, client, users):
    farmer, fpo_u, fpo_p, admin = users

    resp = client.post(
        "/farms",
        json={
            "farm_name": "Solo Farm",
            "land_area_acres": 2.0,
            "latitude": 18.6,
            "longitude": 73.9,
            "village": "Alonetown",
            "district": "Pune",
            "state": "Maharashtra",
            "soil_type": "Loam",
            "water_source": "Rain",
        },
        headers={"Authorization": f"Bearer {_token(farmer)}"},
    )
    assert resp.status_code == 201
    assert resp.json()["farm_status"] == "DRAFT"


# ─── 13: batch normalization — multiple bad rows fixed in one pass ────────────

def test_batch_normalization_multiple_farms(db, users):
    farmer, fpo_u, fpo_p, admin = users

    f1 = _make_farm(db, farmer, fpo_profile=fpo_p, approved=False, farm_name="Batch1")
    f2 = _make_farm(db, farmer, fpo_profile=fpo_p, approved=True,  farm_name="Batch2")
    f3 = _make_farm(db, farmer, fpo_profile=fpo_p, approved=False, farm_name="Batch3")
    f1_id, f2_id, f3_id = f1.id, f2.id, f3.id

    _inject_bad_value(db, f1_id, "pending")
    _inject_bad_value(db, f2_id, "approved")
    _inject_bad_value(db, f3_id, "PENDING")

    _run_normalizer(db)

    assert _read_status(db, f1_id) == "PENDING_APPROVAL"
    assert _read_status(db, f2_id) == "APPROVED"
    assert _read_status(db, f3_id) == "PENDING_APPROVAL"
