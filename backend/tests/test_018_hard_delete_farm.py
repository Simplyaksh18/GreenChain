"""
test_018_hard_delete_farm.py

Tests for hard-delete farm endpoint (DELETE /farms/{farm_id}):
  1. Farmer can permanently delete a plain farm
  2. Deleted farm no longer appears in GET /farms
  3. Farmer cannot delete another farmer's farm (403)
  4. Farm with minted token cannot be deleted (400)
  5. Farm with verified report cannot be deleted (400)
  6. GET /admin/workflow-status returns expected shape
"""
import pytest

from tests.conftest import (
    _make_user, _make_fpo_profile, _make_farm, _make_readings,
)
from app.models.user import UserRole
from app.models.farm import FarmStatus, CropCycle, CropCycleStatus
from app.models.carbon_report import CarbonReport, ReportStatus
from app.models.carbon_token import CarbonToken, TokenStatus
from app.security import create_access_token
from datetime import date


def _token(user) -> str:
    return create_access_token({"sub": str(user.id)})


@pytest.fixture
def setup(db):
    farmer  = _make_user(db, "Del Farmer",  "del_farmer@test.com",  UserRole.FARMER)
    farmer2 = _make_user(db, "Del Farmer2", "del_farmer2@test.com", UserRole.FARMER)
    admin   = _make_user(db, "Del Admin",   "del_admin@test.com",   UserRole.ADMIN)
    fpo_u   = _make_user(db, "Del FPO",     "del_fpo@test.com",     UserRole.FPO)
    fpo_p   = _make_fpo_profile(db, fpo_u, org="DelFPO", reg="DREG001")
    return farmer, farmer2, admin, fpo_u, fpo_p


# ─── 1: Plain farm can be deleted permanently ─────────────────────────────────

def test_farmer_can_hard_delete_own_farm(db, client, setup):
    farmer, farmer2, admin, fpo_u, fpo_p = setup
    farm = _make_farm(db, farmer, farm_name="DeleteMe")
    farm_id = farm.id

    resp = client.delete(
        f"/farms/{farm_id}",
        headers={"Authorization": f"Bearer {_token(farmer)}"},
    )
    assert resp.status_code == 200
    assert "permanently deleted" in resp.json()["message"]


# ─── 2: Farm no longer found after deletion ───────────────────────────────────

def test_deleted_farm_not_found(db, client, setup):
    farmer, farmer2, admin, fpo_u, fpo_p = setup
    farm = _make_farm(db, farmer, farm_name="GoneForever")
    farm_id = farm.id

    client.delete(
        f"/farms/{farm_id}",
        headers={"Authorization": f"Bearer {_token(farmer)}"},
    )

    resp = client.get(
        f"/farms/{farm_id}",
        headers={"Authorization": f"Bearer {_token(farmer)}"},
    )
    assert resp.status_code == 404


# ─── 3: Cannot delete another farmer's farm ──────────────────────────────────

def test_farmer_cannot_delete_others_farm(db, client, setup):
    farmer, farmer2, admin, fpo_u, fpo_p = setup
    farm = _make_farm(db, farmer, farm_name="NotYours")

    resp = client.delete(
        f"/farms/{farm.id}",
        headers={"Authorization": f"Bearer {_token(farmer2)}"},
    )
    assert resp.status_code == 403


# ─── 4: Farm with minted token cannot be deleted ─────────────────────────────

def test_farm_with_minted_token_cannot_be_deleted(db, client, setup):
    farmer, farmer2, admin, fpo_u, fpo_p = setup
    farm = _make_farm(db, farmer, fpo_profile=fpo_p, approved=True, farm_name="Minted Farm")

    # Create a cycle and a minimal verified report
    cycle = CropCycle(
        farm_id=farm.id, crop_type="Paddy", season="K2024",
        start_date=date(2024, 6, 1), end_date=date(2024, 10, 30),
        baseline_method="IPCC", reduction_practice="AWD",
        status=CropCycleStatus.ACTIVE,
    )
    db.add(cycle)
    db.commit()
    db.refresh(cycle)

    report = CarbonReport(
        farm_id=farm.id, crop_cycle_id=cycle.id,
        baseline_methane_kg=100.0, current_methane_kg=70.0, methane_reduction_kg=30.0,
        co2e_reduction_tonnes=0.816, estimated_credits=0,
        report_hash="abc123", status=ReportStatus.VERIFIED,
    )
    db.add(report)
    db.commit()
    db.refresh(report)

    # Simulate a minted token
    import secrets
    token_obj = CarbonToken(
        carbon_report_id=report.id,
        farmer_id=farmer.id,
        token_id=f"GC-TEST-{secrets.token_hex(4)}",
        credit_amount=0,
        status=TokenStatus.MINTED,
        fpo_id=fpo_p.id,
    )
    db.add(token_obj)
    db.commit()

    resp = client.delete(
        f"/farms/{farm.id}",
        headers={"Authorization": f"Bearer {_token(farmer)}"},
    )
    assert resp.status_code == 400
    assert "carbon credits" in resp.json()["detail"].lower()


# ─── 5: Farm with verified report cannot be deleted ──────────────────────────

def test_farm_with_verified_report_cannot_be_deleted(db, client, setup):
    farmer, farmer2, admin, fpo_u, fpo_p = setup
    farm = _make_farm(db, farmer, fpo_profile=fpo_p, approved=True, farm_name="VerifiedFarm")

    cycle = CropCycle(
        farm_id=farm.id, crop_type="Paddy", season="K2024",
        start_date=date(2024, 6, 1), end_date=date(2024, 10, 30),
        baseline_method="IPCC", reduction_practice="AWD",
        status=CropCycleStatus.ACTIVE,
    )
    db.add(cycle)
    db.commit()
    db.refresh(cycle)

    report = CarbonReport(
        farm_id=farm.id, crop_cycle_id=cycle.id,
        baseline_methane_kg=100.0, current_methane_kg=50.0, methane_reduction_kg=50.0,
        co2e_reduction_tonnes=1.36, estimated_credits=1,
        report_hash="def456", status=ReportStatus.VERIFIED,
    )
    db.add(report)
    db.commit()

    resp = client.delete(
        f"/farms/{farm.id}",
        headers={"Authorization": f"Bearer {_token(farmer)}"},
    )
    assert resp.status_code == 400
    assert "verified" in resp.json()["detail"].lower()


# ─── 6: GET /admin/workflow-status returns correct shape ─────────────────────

def test_admin_workflow_status(db, client, setup):
    farmer, farmer2, admin, fpo_u, fpo_p = setup
    _make_farm(db, farmer, fpo_profile=fpo_p, approved=True, farm_name="WS Farm1")

    resp = client.get(
        "/admin/workflow-status",
        headers={"Authorization": f"Bearer {_token(admin)}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    required_keys = {
        "farms_total", "farms_approved",
        "reports_draft", "reports_submitted", "reports_verified",
        "reports_rejected", "reports_mintable", "reports_tokenized",
        "credits_total", "payouts_total",
    }
    assert required_keys.issubset(data.keys())
    assert data["farms_total"] >= 1
    assert data["farms_approved"] >= 1
