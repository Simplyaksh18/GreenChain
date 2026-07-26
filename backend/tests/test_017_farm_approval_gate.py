"""
test_017_farm_approval_gate.py

Tests for the farm approval gate on carbon report submission and verification:
  1. Submitting a DRAFT report for a non-APPROVED farm → 400
  2. Submitting a DRAFT report for an APPROVED farm → 200
  3. Verifier GET /verification/pending excludes non-APPROVED farm reports
  4. Verifier GET /verification/pending includes APPROVED farm reports
  5. GET /verification/{id} for non-APPROVED farm → 400
"""
import pytest

from tests.conftest import (
    TestingSessionLocal,
    _make_user, _make_fpo_profile, _make_farm, _make_readings,
)
from app.models.user import UserRole
from app.models.farm import FarmStatus, CropCycle, CropCycleStatus
from app.models.carbon_report import CarbonReport, ReportStatus
from app.models.verification import VerificationRequest, VerificationStatus
from app.security import create_access_token


def _token(user) -> str:
    return create_access_token({"sub": str(user.id)})


def _make_cycle(db, farm):
    from datetime import date
    cycle = CropCycle(
        farm_id=farm.id,
        crop_type="Paddy",
        season="Kharif 2024",
        start_date=date(2024, 6, 1),
        end_date=date(2024, 10, 30),
        baseline_method="IPCC Tier 1",
        reduction_practice="AWD",
        status=CropCycleStatus.ACTIVE,
    )
    db.add(cycle)
    db.commit()
    db.refresh(cycle)
    return cycle


def _make_report(db, farm, cycle, status=ReportStatus.DRAFT):
    from app.services.carbon_calculator import calculate_carbon_report
    from app.models.sensor import SensorReading
    readings = db.query(SensorReading).filter(SensorReading.crop_cycle_id == cycle.id).all()
    if len(readings) < 7:
        raise ValueError("Need at least 7 readings")
    calc = calculate_carbon_report(readings, farm.id, cycle.id)
    report = CarbonReport(
        farm_id=farm.id,
        crop_cycle_id=cycle.id,
        baseline_methane_kg=calc.baseline_methane_kg,
        current_methane_kg=calc.current_methane_kg,
        methane_reduction_kg=calc.methane_reduction_kg,
        co2e_reduction_tonnes=calc.co2e_reduction_tonnes,
        estimated_credits=calc.estimated_credits,
        report_hash=calc.report_hash,
        status=status,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


def _make_vr(db, report):
    vr = VerificationRequest(
        carbon_report_id=report.id,
        status=VerificationStatus.PENDING,
        risk_score=10.0,
        risk_level="LOW",
        recommendation="APPROVE",
    )
    db.add(vr)
    db.commit()
    db.refresh(vr)
    return vr


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def setup(db):
    farmer = _make_user(db, "Gate Farmer", "gate_farmer@test.com", UserRole.FARMER)
    fpo_u  = _make_user(db, "Gate FPO",   "gate_fpo@test.com",    UserRole.FPO)
    verifier = _make_user(db, "Gate Verifier", "gate_verifier@test.com", UserRole.VERIFIER)
    fpo_p  = _make_fpo_profile(db, fpo_u, org="GateFPO", reg="GREG001")

    approved_farm = _make_farm(db, farmer, fpo_profile=fpo_p, approved=True,
                               farm_name="Gate Approved Farm")
    pending_farm  = _make_farm(db, farmer, fpo_profile=fpo_p, approved=False,
                               farm_name="Gate Pending Farm")
    # Force pending_farm to PENDING_APPROVAL status
    pending_farm.farm_status = FarmStatus.PENDING_APPROVAL
    db.commit()
    db.refresh(pending_farm)

    return farmer, fpo_u, fpo_p, verifier, approved_farm, pending_farm


# ─── 1: Submit report for PENDING_APPROVAL farm → 400 ────────────────────────

def test_submit_report_pending_farm_blocked(db, client, setup):
    farmer, fpo_u, fpo_p, verifier, approved_farm, pending_farm = setup

    cycle = _make_cycle(db, pending_farm)
    _make_readings(db, pending_farm, cycle, count=14)
    report = _make_report(db, pending_farm, cycle, status=ReportStatus.DRAFT)

    resp = client.post(
        f"/carbon-reports/{report.id}/submit",
        headers={"Authorization": f"Bearer {_token(farmer)}"},
    )
    assert resp.status_code == 400
    assert "approved" in resp.json()["detail"].lower()


# ─── 2: Submit report for APPROVED farm → 200 ────────────────────────────────

def test_submit_report_approved_farm_succeeds(db, client, setup):
    farmer, fpo_u, fpo_p, verifier, approved_farm, pending_farm = setup

    cycle = _make_cycle(db, approved_farm)
    _make_readings(db, approved_farm, cycle, count=14)
    report = _make_report(db, approved_farm, cycle, status=ReportStatus.DRAFT)

    resp = client.post(
        f"/carbon-reports/{report.id}/submit",
        headers={"Authorization": f"Bearer {_token(farmer)}"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "SUBMITTED"


# ─── 3: GET /verification/pending excludes non-APPROVED farm reports ──────────

def test_pending_queue_excludes_unapproved_farms(db, client, setup):
    farmer, fpo_u, fpo_p, verifier, approved_farm, pending_farm = setup

    # Create a submitted report for the pending farm (bypass gate via direct DB)
    cycle = _make_cycle(db, pending_farm)
    _make_readings(db, pending_farm, cycle, count=14)
    report = _make_report(db, pending_farm, cycle, status=ReportStatus.SUBMITTED)
    _make_vr(db, report)

    resp = client.get(
        "/verification/pending",
        headers={"Authorization": f"Bearer {_token(verifier)}"},
    )
    assert resp.status_code == 200
    # The VR for the pending farm must not appear
    report_ids = [vr["carbon_report_id"] for vr in resp.json()]
    assert report.id not in report_ids


# ─── 4: GET /verification/pending includes APPROVED farm reports ──────────────

def test_pending_queue_includes_approved_farms(db, client, setup):
    farmer, fpo_u, fpo_p, verifier, approved_farm, pending_farm = setup

    cycle = _make_cycle(db, approved_farm)
    _make_readings(db, approved_farm, cycle, count=14)
    report = _make_report(db, approved_farm, cycle, status=ReportStatus.SUBMITTED)
    vr = _make_vr(db, report)

    resp = client.get(
        "/verification/pending",
        headers={"Authorization": f"Bearer {_token(verifier)}"},
    )
    assert resp.status_code == 200
    report_ids = [v["carbon_report_id"] for v in resp.json()]
    assert report.id in report_ids


# ─── 5: GET /verification/{id} for non-APPROVED farm → 400 ───────────────────

def test_get_verification_unapproved_farm_blocked(db, client, setup):
    farmer, fpo_u, fpo_p, verifier, approved_farm, pending_farm = setup

    cycle = _make_cycle(db, pending_farm)
    _make_readings(db, pending_farm, cycle, count=14)
    report = _make_report(db, pending_farm, cycle, status=ReportStatus.SUBMITTED)
    vr = _make_vr(db, report)

    resp = client.get(
        f"/verification/{vr.id}",
        headers={"Authorization": f"Bearer {_token(verifier)}"},
    )
    assert resp.status_code == 400
    assert "approved" in resp.json()["detail"].lower()
