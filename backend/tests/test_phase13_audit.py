"""
test_phase13_audit.py — Phase 13 Evidence & Audit Trail tests.

Covers:
  34. Payment status returns razorpayx when RAZORPAY_MODE=test + keys set
  35. Payment status never exposes key/secret values
  36. Evidence upload computes SHA-256 hash
  37. Evidence hash verify — hash_match=True for untampered evidence
  38. Evidence by carbon report endpoint works
  39. Farm full audit report returns all major sections
  40. Report audit package returns report + evidence + verification + blockchain
  41. Audit blocked for unauthorized farmer
  42. Evidence upload by verifier is blocked (403)
  43. Methane diagnostics present in report detail
  44. SOC credits excluded from mintable_credits in audit package
"""
from __future__ import annotations

import os
import pytest

from tests.conftest import (
    _make_user, _make_fpo_profile, _make_farm, _make_cycle,
    _make_readings, _make_carbon_report, _make_satellite_observations,
)
from app.models.user import UserRole
from app.models.carbon_report import ReportStatus
from app.models.evidence import EvidenceFile
from app.security import create_access_token


def _tok(user) -> str:
    return create_access_token({"sub": str(user.id)})


def _auth(user) -> dict:
    return {"Authorization": f"Bearer {_tok(user)}"}


# ── Shared fixture ─────────────────────────────────────────────────────────────

@pytest.fixture
def setup(db):
    farmer   = _make_user(db, "A13 Farmer",  "a13_farmer@test.com",  UserRole.FARMER)
    admin    = _make_user(db, "A13 Admin",   "a13_admin@test.com",   UserRole.ADMIN)
    verifier = _make_user(db, "A13 Verif",   "a13_verif@test.com",   UserRole.VERIFIER)
    other    = _make_user(db, "A13 Other",   "a13_other@test.com",   UserRole.FARMER)
    fpo_usr  = _make_user(db, "A13 FPO",     "a13_fpo@test.com",     UserRole.FPO)
    fpo_prof = _make_fpo_profile(db, fpo_usr)
    farm     = _make_farm(db, farmer, fpo_profile=fpo_prof, approved=True)
    cycle    = _make_cycle(db, farm)
    readings = _make_readings(db, farm, cycle, count=14)
    report   = _make_carbon_report(db, farm, cycle, status=ReportStatus.DRAFT)
    return dict(
        farmer=farmer, admin=admin, verifier=verifier, other=other,
        fpo_usr=fpo_usr, fpo_prof=fpo_prof, farm=farm, cycle=cycle,
        readings=readings, report=report,
    )


# ── 34. Payment status returns razorpayx when mode=test ───────────────────────

def test_payment_status_razorpayx_when_mode_test(client, setup):
    """When RAZORPAY_MODE=test and key+secret are set, provider must be razorpayx."""
    # Save original and set test env
    original_mode = os.environ.get("RAZORPAY_MODE")
    original_key  = os.environ.get("RAZORPAY_KEY_ID")
    original_sec  = os.environ.get("RAZORPAY_KEY_SECRET")
    try:
        os.environ["RAZORPAY_MODE"]       = "test"
        os.environ["RAZORPAY_KEY_ID"]     = "rzp_test_TESTKEY"
        os.environ["RAZORPAY_KEY_SECRET"] = "test_secret_value"

        r = client.get("/system/payment-status", headers=_auth(setup["admin"]))
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["provider"] == "razorpayx", f"Expected razorpayx, got: {d['provider']}"
        assert d["mode"] == "test"
        assert d["configured"] is True
    finally:
        # Restore originals
        if original_mode is not None:
            os.environ["RAZORPAY_MODE"] = original_mode
        elif "RAZORPAY_MODE" in os.environ:
            del os.environ["RAZORPAY_MODE"]
        if original_key is not None:
            os.environ["RAZORPAY_KEY_ID"] = original_key
        elif "RAZORPAY_KEY_ID" in os.environ:
            del os.environ["RAZORPAY_KEY_ID"]
        if original_sec is not None:
            os.environ["RAZORPAY_KEY_SECRET"] = original_sec
        elif "RAZORPAY_KEY_SECRET" in os.environ:
            del os.environ["RAZORPAY_KEY_SECRET"]


# ── 35. Payment status never exposes key/secret values ────────────────────────

def test_payment_status_no_secrets(client, setup):
    """Response must be boolean flags only — never actual key or secret values."""
    r = client.get("/system/payment-status", headers=_auth(setup["admin"]))
    assert r.status_code == 200, r.text
    raw = str(r.json())
    assert "rzp_test" not in raw
    assert "rzp_live" not in raw
    # The value of RAZORPAY_KEY_SECRET must never appear in any field
    secret = os.environ.get("RAZORPAY_KEY_SECRET", "")
    if secret:
        assert secret not in raw


# ── 36. Evidence upload computes SHA-256 hash ─────────────────────────────────

def test_evidence_upload_computes_hash(client, setup):
    farm, cycle = setup["farm"], setup["cycle"]
    payload = {
        "farm_id": farm.id,
        "crop_cycle_id": cycle.id,
        "file_url": "https://storage.example.com/evidence/field_photo.jpg",
        "file_type": "IMAGE",
        "description": "Field photo taken at planting",
    }
    r = client.post("/evidence", json=payload, headers=_auth(setup["farmer"]))
    assert r.status_code == 201, r.text
    d = r.json()
    assert d["file_hash"] is not None, "file_hash must be computed"
    assert len(d["file_hash"]) == 64, "SHA-256 produces 64 hex chars"
    assert d["hash_algorithm"] == "SHA256"


# ── 37. Evidence hash verify — hash_match=True for untampered evidence ─────────

def test_evidence_hash_verify_match(client, setup):
    farm, cycle = setup["farm"], setup["cycle"]
    create_r = client.post(
        "/evidence",
        json={
            "farm_id": farm.id,
            "crop_cycle_id": cycle.id,
            "file_url": "https://storage.example.com/evidence/soil_test.pdf",
            "file_type": "PDF",
            "description": "Lab SOC test certificate",
        },
        headers=_auth(setup["farmer"]),
    )
    assert create_r.status_code == 201, create_r.text
    ev_id = create_r.json()["id"]

    verify_r = client.get(f"/evidence/{ev_id}/verify", headers=_auth(setup["admin"]))
    assert verify_r.status_code == 200, verify_r.text
    vd = verify_r.json()
    assert vd["hash_match"] is True
    assert vd["stored_hash"] == vd["recomputed_hash"]
    assert len(vd["recomputed_hash"]) == 64
    assert "verified_at" in vd


# ── 38. Evidence by carbon report ────────────────────────────────────────────

def test_evidence_by_report(client, setup):
    farm, cycle, report = setup["farm"], setup["cycle"], setup["report"]
    # Upload evidence linked to the carbon report
    client.post(
        "/evidence",
        json={
            "farm_id": farm.id,
            "crop_cycle_id": cycle.id,
            "carbon_report_id": report.id,
            "file_url": "https://storage.example.com/report_doc.pdf",
            "file_type": "PDF",
            "description": "Carbon report supporting doc",
        },
        headers=_auth(setup["farmer"]),
    )
    r = client.get(f"/evidence/report/{report.id}", headers=_auth(setup["admin"]))
    assert r.status_code == 200, r.text
    items = r.json()
    assert len(items) >= 1
    assert any(e["carbon_report_id"] == report.id for e in items)


# ── 39. Farm full audit report returns all major sections ─────────────────────

def test_farm_full_audit_structure(client, setup, db):
    farm = setup["farm"]
    _make_satellite_observations(db, farm, setup["cycle"], count=5)
    r = client.get(f"/audit/farms/{farm.id}/full-report", headers=_auth(setup["admin"]))
    assert r.status_code == 200, r.text
    d = r.json()
    for key in ("farm", "crop_cycles", "carbon_reports", "soc_reports",
                "evidence", "payouts", "methodology", "generated_at"):
        assert key in d, f"Missing audit section: {key}"
    assert "methane" in d["methodology"]
    assert "soc" in d["methodology"]
    assert d["farm"]["id"] == farm.id
    # SOC credits must always be informational in the audit export
    for sr in d.get("soc_reports", []):
        assert sr["is_informational_only"] is True


# ── 40. Report audit package structure ────────────────────────────────────────

def test_report_audit_package_structure(client, setup):
    report = setup["report"]
    r = client.get(f"/audit/reports/{report.id}/package", headers=_auth(setup["admin"]))
    assert r.status_code == 200, r.text
    d = r.json()
    for key in ("carbon_report", "methane_diagnostics", "crop_cycle",
                "evidence", "verification_history", "blockchain_transactions",
                "token", "methodology", "generated_at"):
        assert key in d, f"Missing report audit key: {key}"
    md = d["methane_diagnostics"]
    assert "baseline_methane_kg" in md
    assert "gwp_factor_used" in md
    assert "formula" in md
    assert "input_sensor_count" in md


# ── 41. Audit blocked for unauthorized farmer ─────────────────────────────────

def test_farm_audit_unauthorized_farmer(client, setup):
    farm = setup["farm"]
    # setup["other"] is a different farmer who doesn't own this farm
    r = client.get(f"/audit/farms/{farm.id}/full-report", headers=_auth(setup["other"]))
    assert r.status_code == 403


# ── 42. Evidence upload by verifier is blocked ───────────────────────────────

def test_evidence_upload_blocked_for_verifier(client, setup):
    farm, cycle = setup["farm"], setup["cycle"]
    r = client.post(
        "/evidence",
        json={
            "farm_id": farm.id,
            "crop_cycle_id": cycle.id,
            "file_url": "https://example.com/blocked.jpg",
            "file_type": "IMAGE",
        },
        headers=_auth(setup["verifier"]),
    )
    assert r.status_code == 403


# ── 43. Methane diagnostics present in report detail ─────────────────────────

def test_methane_diagnostics_in_report_detail(client, setup):
    report = setup["report"]
    r = client.get(f"/carbon-reports/{report.id}/detail", headers=_auth(setup["admin"]))
    assert r.status_code == 200, r.text
    d = r.json()
    assert "methane_diagnostics" in d, "methane_diagnostics section must be present"
    md = d["methane_diagnostics"]
    assert "gwp_factor" in md
    assert "formula" in md
    assert "input_sensor_count" in md
    assert "methodology" in md


# ── 44. SOC credits excluded from mintable_credits ───────────────────────────

def test_soc_credits_not_in_mintable_credits(client, setup, db):
    farm, cycle = setup["farm"], setup["cycle"]
    _make_satellite_observations(db, farm, cycle, count=5)
    r = client.get(
        f"/soc/farms/{farm.id}/crop-cycles/{cycle.id}/combined",
        headers=_auth(setup["farmer"]),
    )
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["mintable_credits"] == d["methane_credits"], (
        "mintable_credits must equal methane_credits only — SOC credits must not be included"
    )
    assert d["soc_section"]["is_informational_only"] is True
