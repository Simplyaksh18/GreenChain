"""
Phase 10A — Secure Custodial Payout UX + Wallet Privacy tests.

Covers:
- FPO wallet masking (mask helper + API response)
- FPO wallet verification (mock mode)
- Wallet address change resets verification
- Payout details masking (UPI + bank account)
- Payout details format verification endpoint
- FPO payout-details endpoint masks UPI (never exposes raw UPI)
- Payout provider: MockPayoutProvider smoke test
- FarmerPayoutDetailsResponse.from_orm_masked returns masked fields
"""
import pytest
from datetime import datetime, timezone

from app.schemas.fpo_schema import _mask_wallet, FPOWalletResponse
from app.schemas.farmer_profile_schema import _mask_upi, _mask_account, FarmerPayoutDetailsResponse
from app.models.fpo import FPOProfile
from app.models.farmer_profile import FarmerProfile, PayoutMethod
from app.models.user import UserRole
from app.services.payout_provider import MockPayoutProvider, PayoutRequest, get_payout_provider


# ── Helper ─────────────────────────────────────────────────────────────────────

def _login(client, email="farmer@test.com", password="password123"):
    resp = client.post("/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    return resp.json()["access_token"]


def _auth(client, email, password="password123"):
    return {"Authorization": f"Bearer {_login(client, email, password)}"}


# ── Wallet masking helpers ─────────────────────────────────────────────────────

class TestWalletMasking:
    def test_mask_wallet_standard_address(self):
        addr = "0xbf26a9c94b585851baed095be140d3792d5ad68c"
        masked = _mask_wallet(addr)
        # first 6 chars = "0xbf26", last 6 chars = "5ad68c"
        assert masked == "0xbf26...5ad68c"
        assert masked.startswith("0xbf26")
        assert "..." in masked
        assert masked.endswith("5ad68c")

    def test_mask_wallet_none_returns_none(self):
        assert _mask_wallet(None) is None

    def test_mask_wallet_short_address_unchanged(self):
        addr = "0x1234"
        masked = _mask_wallet(addr)
        assert masked == addr  # too short to mask

    def test_mask_wallet_full_42_char_address(self):
        addr = "0x" + "a" * 40
        masked = _mask_wallet(addr)
        assert masked.startswith("0xaaaa")
        assert masked.endswith("aaaaaa")
        assert "..." in masked


# ── UPI masking helpers ────────────────────────────────────────────────────────

class TestUpiMasking:
    def test_mask_upi_standard(self):
        assert _mask_upi("abc@okicici") == "a***@okicici"

    def test_mask_upi_short_local(self):
        assert _mask_upi("a@upi") == "a***@upi"

    def test_mask_upi_empty_local(self):
        result = _mask_upi("@upi")
        assert result == "***@upi"

    def test_mask_upi_none_returns_none(self):
        assert _mask_upi(None) is None

    def test_mask_upi_no_at_sign(self):
        result = _mask_upi("invalidupi")
        assert result == "***"

    def test_mask_upi_long_local(self):
        result = _mask_upi("ramanan.farmer@okhdfc")
        assert result == "r***@okhdfc"


# ── Bank account masking ───────────────────────────────────────────────────────

class TestBankMasking:
    def test_mask_account_standard(self):
        result = _mask_account("123456789012")
        assert result == "********9012"
        assert result.endswith("9012")

    def test_mask_account_short(self):
        result = _mask_account("1234")
        assert result == "1234"   # only 4 chars, all visible

    def test_mask_account_none(self):
        assert _mask_account(None) is None


# ── FPO wallet verification — mock mode ───────────────────────────────────────

class TestFPOWalletVerify:
    def test_verify_valid_wallet_mock_mode(self, client, db, fpo_user, fpo_profile):
        # Set wallet address on profile
        fpo_profile.wallet_address = "0xbf26a9c94b585851baed095be140d3792d5ad68c"
        db.commit()

        headers = _auth(client, "fpo@test.com")
        resp = client.post("/fpo/profile/wallet/verify", headers=headers, json={})
        assert resp.status_code == 200
        data = resp.json()
        assert data["verified"] is True
        assert data["wallet_address"] == "0xbf26a9c94b585851baed095be140d3792d5ad68c"
        assert "..." in data["wallet_address_masked"]
        assert data["wallet_network"] is not None
        assert "verified_at" in data
        assert "mock" in data["message"].lower() or "verified" in data["message"].lower()

    def test_verify_no_wallet_raises_400(self, client, db, fpo_user, fpo_profile):
        headers = _auth(client, "fpo@test.com")
        resp = client.post("/fpo/profile/wallet/verify", headers=headers, json={})
        assert resp.status_code == 400
        assert "wallet address" in resp.json()["detail"].lower()

    def test_verify_no_profile_raises_404(self, client, db, fpo_user):
        headers = _auth(client, "fpo@test.com")
        resp = client.post("/fpo/profile/wallet/verify", headers=headers, json={})
        assert resp.status_code == 404

    def test_farmer_cannot_call_wallet_verify(self, client, db, farmer_user):
        headers = _auth(client, "farmer@test.com")
        resp = client.post("/fpo/profile/wallet/verify", headers=headers, json={})
        assert resp.status_code in (403, 401)

    def test_wallet_verified_persists_in_get_wallet(self, client, db, fpo_user, fpo_profile):
        fpo_profile.wallet_address = "0xbf26a9c94b585851baed095be140d3792d5ad68c"
        fpo_profile.wallet_verified = True
        fpo_profile.wallet_verified_at = datetime.now(timezone.utc)
        db.commit()

        headers = _auth(client, "fpo@test.com")
        resp = client.get("/fpo/profile/wallet", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["wallet_verified"] is True
        assert data["wallet_address_masked"] is not None
        assert "..." in data["wallet_address_masked"]

    def test_changing_wallet_resets_verification(self, client, db, fpo_user, fpo_profile):
        fpo_profile.wallet_address = "0xbf26a9c94b585851baed095be140d3792d5ad68c"
        fpo_profile.wallet_verified = True
        db.commit()

        headers = _auth(client, "fpo@test.com")
        new_addr = "0x" + "b" * 40
        resp = client.patch(
            "/fpo/profile/wallet",
            headers=headers,
            json={"wallet_address": new_addr},
        )
        assert resp.status_code == 200
        assert resp.json()["wallet_verified"] is False


# ── Payout details masking ─────────────────────────────────────────────────────

class TestPayoutDetailsMasking:
    def test_upsert_upi_returns_masked(self, client, db, farmer_user):
        headers = _auth(client, "farmer@test.com")
        resp = client.post(
            "/farmers/payout-details",
            headers=headers,
            json={
                "preferred_payout_method": "UPI",
                "upi_id": "ramanan@okicici",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        # raw upi_id should NOT appear in response
        assert "upi_id" not in data or data.get("upi_id") is None
        assert "upi_id_masked" in data
        assert data["upi_id_masked"] == "r***@okicici"

    def test_upsert_bank_returns_masked(self, client, db, farmer_user):
        headers = _auth(client, "farmer@test.com")
        resp = client.post(
            "/farmers/payout-details",
            headers=headers,
            json={
                "preferred_payout_method": "BANK_TRANSFER",
                "bank_account_holder_name": "Ramanan Kumar",
                "bank_account_number": "123456789012",
                "ifsc_code": "HDFC0001234",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["bank_account_number_masked"] == "********9012"
        # Verify raw bank number is never returned
        assert "bank_account_number" not in data or data.get("bank_account_number") is None

    def test_from_orm_masked_masks_both(self, db, farmer_user):
        profile = FarmerProfile(
            user_id=farmer_user.id,
            preferred_payout_method=PayoutMethod.UPI,
            upi_id="test@okicici",
            bank_account_number="987654321",
        )
        db.add(profile)
        db.commit()
        db.refresh(profile)

        resp = FarmerPayoutDetailsResponse.from_orm_masked(profile)
        assert resp.upi_id_masked == "t***@okicici"
        assert resp.bank_account_number_masked == "*****4321"


# ── Payout details verification endpoint ──────────────────────────────────────

class TestPayoutDetailsVerify:
    def test_verify_upi_format(self, client, db, farmer_user):
        headers = _auth(client, "farmer@test.com")
        # Set up UPI details
        client.post(
            "/farmers/payout-details",
            headers=headers,
            json={"preferred_payout_method": "UPI", "upi_id": "ramanan@okicici"},
        )
        resp = client.post("/farmers/payout-details/verify", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["payout_details_verified"] is True
        assert data["payout_verification_method"] == "FORMAT_CHECK"
        assert data["payout_details_verified_at"] is not None

    def test_verify_bank_format(self, client, db, farmer_user):
        headers = _auth(client, "farmer@test.com")
        client.post(
            "/farmers/payout-details",
            headers=headers,
            json={
                "preferred_payout_method": "BANK_TRANSFER",
                "bank_account_holder_name": "Ramanan Kumar",
                "bank_account_number": "123456789012",
                "ifsc_code": "HDFC0001234",
            },
        )
        resp = client.post("/farmers/payout-details/verify", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["payout_details_verified"] is True

    def test_verify_no_details_returns_404(self, client, db, farmer_user):
        headers = _auth(client, "farmer@test.com")
        resp = client.post("/farmers/payout-details/verify", headers=headers)
        assert resp.status_code == 404

    def test_verify_missing_upi_id_fails(self, client, db, farmer_user):
        headers = _auth(client, "farmer@test.com")
        client.post(
            "/farmers/payout-details",
            headers=headers,
            json={"preferred_payout_method": "UPI"},  # no upi_id
        )
        resp = client.post("/farmers/payout-details/verify", headers=headers)
        assert resp.status_code == 422
        assert "UPI" in resp.json()["detail"]

    def test_fpo_cannot_call_verify(self, client, db, fpo_user, fpo_profile):
        headers = _auth(client, "fpo@test.com")
        resp = client.post("/farmers/payout-details/verify", headers=headers)
        assert resp.status_code in (403, 401)


# ── FPO payout-details endpoint masks UPI ─────────────────────────────────────

class TestFPOPayoutDetailsUPIMask:
    def test_fpo_payout_details_returns_masked_upi(
        self, client, db, fpo_user, fpo_profile, farmer_user
    ):
        from app.models.farm import Farm, CropCycle
        from app.models.carbon_report import CarbonReport, ReportStatus
        from app.models.farmer_credit_balance import FarmerCreditBalance, CreditBalanceStatus

        # Link farm to FPO
        farm = Farm(
            farmer_id=farmer_user.id,
            fpo_id=fpo_profile.id,
            farm_name="Test Farm",
            village="TestVillage",
            district="TestDistrict",
            state="MH",
            land_area_acres=5.0,
            latitude=18.5,
            longitude=73.8,
            soil_type="Loamy",
            water_source="Rain",
            is_approved=True,
        )
        db.add(farm)
        db.commit()
        db.refresh(farm)

        cycle = CropCycle(
            farm_id=farm.id,
            crop_type="Wheat",
            season="Kharif",
            start_date=datetime.now(timezone.utc),
            baseline_method="IPCC_TIER1",
            reduction_practice="SRI",
        )
        db.add(cycle)
        db.commit()
        db.refresh(cycle)

        report = CarbonReport(
            farm_id=farm.id,
            crop_cycle_id=cycle.id,
            status=ReportStatus.VERIFIED,
            estimated_credits=5,
            baseline_methane_kg=100.0,
            current_methane_kg=80.0,
            methane_reduction_kg=20.0,
            co2e_reduction_tonnes=0.42,
            report_hash="0x" + "a" * 64,
        )
        db.add(report)
        db.commit()
        db.refresh(report)

        balance = FarmerCreditBalance(
            farmer_id=farmer_user.id,
            fpo_id=fpo_profile.id,
            carbon_report_id=report.id,
            credits_earned=5,
            credits_available=5,
            credits_distributed=0,
            status=CreditBalanceStatus.TOKENIZED,
        )
        db.add(balance)

        # Farmer has UPI details
        profile = FarmerProfile(
            user_id=farmer_user.id,
            preferred_payout_method=PayoutMethod.UPI,
            upi_id="alice@okicici",
        )
        db.add(profile)
        db.commit()
        db.refresh(balance)

        headers = _auth(client, "fpo@test.com")
        resp = client.get(f"/fpo/credits/farmers/{balance.id}/payout-details", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        # Raw UPI must never appear
        assert "alice@okicici" not in str(data)
        # Masked UPI should appear
        assert data.get("upi_id_masked") == "a***@okicici"


# ── Payout provider smoke test ────────────────────────────────────────────────

class TestPayoutProvider:
    def test_mock_provider_returns_success(self):
        provider = MockPayoutProvider()
        req = PayoutRequest(
            payout_id=1,
            idempotency_key="test-key-001",
            amount_paise=5000,
            currency="INR",
            payout_method="UPI",
            masked_destination="r***@okicici",
            farmer_name="Ramanan Kumar",
        )
        result = provider.process_payout(req)
        assert result.success is True
        assert result.provider_reference_id is not None
        assert result.provider_reference_id.startswith("MOCK-PAY-")
        assert result.simulated is True

    def test_mock_provider_check_status(self):
        provider = MockPayoutProvider()
        status = provider.check_status("MOCK-PAY-1-ABCD1234")
        assert status == "COMPLETED"

    def test_mock_provider_check_status_unknown(self):
        provider = MockPayoutProvider()
        status = provider.check_status("LIVE-PAY-UNKNOWN")
        assert status == "FAILED"

    def test_get_payout_provider_returns_mock_by_default(self, monkeypatch):
        monkeypatch.delenv("RAZORPAY_MODE", raising=False)
        provider = get_payout_provider()
        assert isinstance(provider, MockPayoutProvider)

    def test_get_payout_provider_mock_explicit(self, monkeypatch):
        monkeypatch.setenv("RAZORPAY_MODE", "mock")
        provider = get_payout_provider()
        assert isinstance(provider, MockPayoutProvider)
