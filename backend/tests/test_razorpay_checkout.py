"""
Phase 17 — Razorpay Checkout tests.

Tests are fully self-contained — they create their own users/data with unique
email addresses (rz_* prefix) so they never collide with conftest shared fixtures.

Coverage:
  1. create-order returns order_id and key_id (never key_secret)
  2. amount_paise = amount_rupees × 100
  3. Verify succeeds → payout COMPLETED, RazorpayPayment COMPLETED
  4. Invalid signature → 400, ledger unchanged
  5. Non-owner FPO cannot create order for another FPO's payout
  6. key_secret is NOT in the create-order response body
"""
import hashlib
import hmac
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from app.models.carbon_report import CarbonReport, ReportStatus
from app.models.carbon_token import CarbonToken, TokenStatus
from app.models.farm import Farm, FarmStatus
from app.models.farm import CropCycle
from app.models.farmer_credit_balance import FarmerCreditBalance, CreditBalanceStatus
from app.models.fpo import FPOProfile
from app.models.payout import Payout, PayoutStatus
from app.models.razorpay_payment import RazorpayPayment, RazorpayPaymentStatus
from app.models.user import User, UserRole
from app.security import hash_password

# ── Constants ─────────────────────────────────────────────────────────────────

TEST_KEY_ID     = "rzp_test_TESTKEY"
TEST_KEY_SECRET = "test_secret_abc123"
FAKE_ORDER_ID   = "order_FakeOrderId123"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_signature(order_id: str, payment_id: str, secret: str) -> str:
    msg = f"{order_id}|{payment_id}"
    return hmac.new(
        secret.encode("utf-8"),
        msg.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _login(client, email, password="password123"):
    resp = client.post("/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _patch_env(monkeypatch):
    """Monkeypatch _razorpay_env to return test credentials."""
    def fake_env(key):
        return {
            "RAZORPAY_KEY_ID":     TEST_KEY_ID,
            "RAZORPAY_KEY_SECRET": TEST_KEY_SECRET,
        }.get(key, "")
    monkeypatch.setattr("app.routers.payments._razorpay_env", fake_env)


def _patch_client(monkeypatch, order_id=FAKE_ORDER_ID):
    mock_client = MagicMock()
    mock_client.order.create.return_value = {"id": order_id}
    monkeypatch.setattr("app.routers.payments._get_razorpay_client", lambda: mock_client)
    return mock_client


# ── Self-contained fixture stack (unique rz_ emails) ─────────────────────────

@pytest.fixture
def rz_fpo(db):
    """FPO user + profile with unique email."""
    u = User(
        name="RZ FPO",
        email="rz_fpo@test.com",
        password_hash=hash_password("password123"),
        role=UserRole.FPO,
        is_active=True,
        is_approved=True,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    p = FPOProfile(user_id=u.id, organization_name="RZ FPO Org",
                   registration_number="RZ001", district="Pune", state="MH")
    db.add(p)
    db.commit()
    db.refresh(p)
    return u, p


@pytest.fixture
def rz_farmer(db, rz_fpo):
    """Farmer user with farm, crop cycle, carbon report, token, and credit balance."""
    _, fpo_profile = rz_fpo
    u = User(
        name="RZ Farmer",
        email="rz_farmer@test.com",
        password_hash=hash_password("password123"),
        role=UserRole.FARMER,
        is_active=True,
        is_approved=True,
    )
    db.add(u)
    db.commit()
    db.refresh(u)

    farm = Farm(
        farmer_id=u.id, fpo_id=fpo_profile.id,
        farm_name="RZ Farm", land_area_acres=3.0,
        latitude=18.5, longitude=73.8, village="RZVillage",
        district="Pune", state="Maharashtra",
        soil_type="Clay", water_source="River",
        is_approved=True, farm_status=FarmStatus.APPROVED,
    )
    db.add(farm)
    db.commit()
    db.refresh(farm)

    cycle = CropCycle(
        farm_id=farm.id, crop_type="Paddy", season="Kharif",
        start_date=datetime(2024, 6, 1).date(),
        baseline_method="AWD", reduction_practice="SRI",
    )
    db.add(cycle)
    db.commit()
    db.refresh(cycle)

    report = CarbonReport(
        farm_id=farm.id, crop_cycle_id=cycle.id,
        baseline_methane_kg=120.0, current_methane_kg=90.0,
        methane_reduction_kg=30.0, co2e_reduction_tonnes=0.75,
        estimated_credits=15, report_hash="rzhash001",
        status=ReportStatus.VERIFIED,
    )
    db.add(report)
    db.commit()
    db.refresh(report)

    import uuid
    token = CarbonToken(
        carbon_report_id=report.id,
        farmer_id=u.id,
        fpo_id=fpo_profile.id,
        token_id=f"rz-tok-{uuid.uuid4().hex[:8]}",
        credit_amount=15,
        status=TokenStatus.MINTED,
    )
    db.add(token)
    db.commit()
    db.refresh(token)

    bal = FarmerCreditBalance(
        farmer_id=u.id, fpo_id=fpo_profile.id,
        carbon_report_id=report.id, carbon_token_id=token.id,
        credits_earned=15, credits_available=15, credits_distributed=0,
        status=CreditBalanceStatus.TOKENIZED,
    )
    db.add(bal)
    db.commit()
    db.refresh(bal)

    return u, farm, cycle, report, token, bal


@pytest.fixture
def rz_payout(db, rz_fpo, rz_farmer):
    """INITIATED payout owned by rz_fpo."""
    fpo_user, fpo_profile = rz_fpo
    farmer_user, _, _, _, _, bal = rz_farmer
    payout = Payout(
        fpo_id=fpo_profile.id,
        farmer_id=farmer_user.id,
        credit_balance_id=bal.id,
        amount_credits=5,
        price_per_credit=1000,   # ₹10 per credit (in paise)
        payout_amount=5000,      # ₹50 total (in paise)
        status=PayoutStatus.INITIATED,
        initiated_by=fpo_user.id,
    )
    db.add(payout)
    db.commit()
    db.refresh(payout)
    return payout


# ── Test 1: create-order returns order_id and key_id ─────────────────────────

def test_create_order_returns_order_id_and_key_id(
    client, monkeypatch, rz_fpo, rz_payout
):
    _patch_env(monkeypatch)
    _patch_client(monkeypatch)
    fpo_user, _ = rz_fpo
    token = _login(client, fpo_user.email)

    resp = client.post(
        "/payments/razorpay/create-order",
        json={
            "purpose":      "FARMER_PAYOUT",
            "reference_id": rz_payout.id,
            "amount":       500,    # ₹500
            "currency":     "INR",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()

    assert data["order_id"] == FAKE_ORDER_ID
    assert data["key_id"] == TEST_KEY_ID
    assert "key_secret" not in data              # security: never expose secret
    assert data["amount_paise"] == 500 * 100     # ₹500 → 50000 paise
    assert data["payment_record_id"] > 0


# ── Test 2: amount_paise = amount_rupees × 100 ────────────────────────────────

def test_amount_paise_conversion(
    client, monkeypatch, rz_fpo, rz_payout
):
    _patch_env(monkeypatch)
    _patch_client(monkeypatch)
    fpo_user, _ = rz_fpo
    token = _login(client, fpo_user.email)

    resp = client.post(
        "/payments/razorpay/create-order",
        json={
            "purpose":      "FARMER_PAYOUT",
            "reference_id": rz_payout.id,
            "amount":       300,   # ₹300
            "currency":     "INR",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["amount_paise"] == 300 * 100   # 30000 paise


# ── Test 3: verify success → payout COMPLETED ─────────────────────────────────

def test_verify_success_marks_payout_completed(
    client, db, monkeypatch, rz_fpo, rz_payout
):
    _patch_env(monkeypatch)
    _patch_client(monkeypatch)
    fpo_user, _ = rz_fpo
    token = _login(client, fpo_user.email)

    # Step 1: create order
    resp = client.post(
        "/payments/razorpay/create-order",
        json={
            "purpose":      "FARMER_PAYOUT",
            "reference_id": rz_payout.id,
            "amount":       500,
            "currency":     "INR",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    order_data = resp.json()

    # Step 2: craft valid HMAC
    fake_payment_id = "pay_TestRZPayId456"
    sig = _make_signature(order_data["order_id"], fake_payment_id, TEST_KEY_SECRET)

    # Step 3: verify
    verify_resp = client.post(
        "/payments/razorpay/verify",
        json={
            "payment_record_id":   order_data["payment_record_id"],
            "razorpay_order_id":   order_data["order_id"],
            "razorpay_payment_id": fake_payment_id,
            "razorpay_signature":  sig,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert verify_resp.status_code == 200, verify_resp.text
    vdata = verify_resp.json()
    assert vdata["status"] == "COMPLETED"
    assert vdata["signature_verified"] is True
    assert vdata["razorpay_payment_id"] == fake_payment_id

    # Payout marked COMPLETED in DB
    db.expire_all()
    db.refresh(rz_payout)
    assert rz_payout.status == PayoutStatus.COMPLETED
    assert rz_payout.provider_reference_id == fake_payment_id


# ── Test 4: invalid signature → 400, ledger unchanged ────────────────────────

def test_invalid_signature_rejected(
    client, db, monkeypatch, rz_fpo, rz_payout
):
    _patch_env(monkeypatch)
    _patch_client(monkeypatch)
    fpo_user, _ = rz_fpo
    token = _login(client, fpo_user.email)

    resp = client.post(
        "/payments/razorpay/create-order",
        json={
            "purpose":      "FARMER_PAYOUT",
            "reference_id": rz_payout.id,
            "amount":       500,
            "currency":     "INR",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    order_data = resp.json()

    # Wrong signature
    verify_resp = client.post(
        "/payments/razorpay/verify",
        json={
            "payment_record_id":   order_data["payment_record_id"],
            "razorpay_order_id":   order_data["order_id"],
            "razorpay_payment_id": "pay_WrongId",
            "razorpay_signature":  "completely_wrong_sig",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert verify_resp.status_code == 400, verify_resp.text
    assert "signature" in verify_resp.json()["detail"].lower()

    # Payout must still be INITIATED
    db.expire_all()
    db.refresh(rz_payout)
    assert rz_payout.status == PayoutStatus.INITIATED

    # RazorpayPayment must be FAILED
    rz = db.query(RazorpayPayment).filter(
        RazorpayPayment.id == order_data["payment_record_id"]
    ).first()
    assert rz is not None
    assert rz.status == RazorpayPaymentStatus.FAILED
    assert rz.signature_verified is False


# ── Test 5: key_secret never in response ─────────────────────────────────────

def test_key_secret_never_in_response(
    client, monkeypatch, rz_fpo, rz_payout
):
    _patch_env(monkeypatch)
    _patch_client(monkeypatch)
    fpo_user, _ = rz_fpo
    token = _login(client, fpo_user.email)

    resp = client.post(
        "/payments/razorpay/create-order",
        json={
            "purpose":      "FARMER_PAYOUT",
            "reference_id": rz_payout.id,
            "amount":       200,
            "currency":     "INR",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    raw = resp.text
    assert TEST_KEY_SECRET not in raw, "key_secret leaked in response!"
    assert "key_secret" not in raw.lower()


# ── Test 6: wrong FPO cannot create order for another FPO's payout ───────────

def test_wrong_fpo_cannot_create_order(
    client, db, monkeypatch, rz_payout
):
    _patch_env(monkeypatch)
    _patch_client(monkeypatch)

    # Second FPO that does NOT own rz_payout
    other = User(
        name="Other FPO",
        email="rz_otherfpo@test.com",
        password_hash=hash_password("password123"),
        role=UserRole.FPO,
        is_active=True,
        is_approved=True,
    )
    db.add(other)
    db.commit()
    db.refresh(other)
    other_profile = FPOProfile(
        user_id=other.id, organization_name="Other RZ Org",
        registration_number="RZ999", district="Mumbai", state="MH",
    )
    db.add(other_profile)
    db.commit()

    other_token = _login(client, other.email)
    resp = client.post(
        "/payments/razorpay/create-order",
        json={
            "purpose":      "FARMER_PAYOUT",
            "reference_id": rz_payout.id,
            "amount":       500,
            "currency":     "INR",
        },
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert resp.status_code == 403, resp.text
