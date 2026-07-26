"""
Phase 10B — Razorpay test-mode preparation tests.

Covers:
- /system/payment-status never exposes credentials
- MockPayoutProvider: config status
- RazorpayXPayoutProvider: config validation, execution disabled by default
- get_payout_provider() factory respects RAZORPAY_MODE
- RazorpayX process_payout returns disabled message (not error) when execution off
- /credits/my-balance returns correct zero values for certificate-only balances
- Mock payout still works end-to-end
"""
import os
import pytest

from app.services.payout_provider import (
    MockPayoutProvider, RazorpayXPayoutProvider, PayoutRequest, get_payout_provider,
)


def _login(client, email="farmer@test.com", password="password123"):
    resp = client.post("/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    return resp.json()["access_token"]

def _auth(client, email, password="password123"):
    return {"Authorization": f"Bearer {_login(client, email, password)}"}


# ── /system/payment-status — no secrets ───────────────────────────────────────

class TestPaymentStatusEndpoint:
    def test_requires_auth(self, client):
        resp = client.get("/system/payment-status")
        assert resp.status_code in (401, 403)

    def test_mock_mode_response(self, client, db, farmer_user, monkeypatch):
        monkeypatch.setenv("RAZORPAY_MODE", "mock")
        headers = _auth(client, "farmer@test.com")
        resp = client.get("/system/payment-status", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["provider"] == "mock"
        assert data["mode"] == "mock"
        assert data["configured"] is True
        assert data["simulated"] is True
        # Must not contain any credential values
        assert "key" not in str(data).lower() or "key_id_set" in data  # bool flag is OK
        for field_name, field_value in data.items():
            # No string value should look like an API key (length > 20, starts with rz)
            if isinstance(field_value, str) and len(field_value) > 20:
                assert not field_value.startswith("rzp_"), \
                    f"Potential Razorpay secret exposed in field {field_name}"

    def test_razorpay_test_mode_no_secret_exposed(self, client, db, farmer_user, monkeypatch):
        monkeypatch.setenv("RAZORPAY_MODE", "test")
        monkeypatch.setenv("RAZORPAY_KEY_ID", "rzp_test_FAKEKEYID123")
        monkeypatch.setenv("RAZORPAY_KEY_SECRET", "SUPER_SECRET_DO_NOT_EXPOSE")
        monkeypatch.delenv("RAZORPAY_ENABLE_TEST_PAYOUTS", raising=False)

        headers = _auth(client, "farmer@test.com")
        resp = client.get("/system/payment-status", headers=headers)
        assert resp.status_code == 200
        data = resp.json()

        # Secret must never appear in response
        response_str = str(data)
        assert "SUPER_SECRET_DO_NOT_EXPOSE" not in response_str
        assert "FAKEKEYID123" not in response_str  # key_id also should not be exposed raw

        assert data["provider"] == "razorpayx"
        assert data["mode"] == "test"
        assert data["configured"] is True
        assert data["secret_set"] is True        # bool flag is OK
        assert data["key_id_set"] is True        # bool flag is OK
        assert data["execution_enabled"] is False  # disabled by default
        assert data["simulated"] is False

    def test_execution_disabled_by_default(self, client, db, farmer_user, monkeypatch):
        monkeypatch.setenv("RAZORPAY_MODE", "test")
        monkeypatch.setenv("RAZORPAY_KEY_ID", "rzp_test_FAKEKEYID")
        monkeypatch.setenv("RAZORPAY_KEY_SECRET", "secret123")
        monkeypatch.delenv("RAZORPAY_ENABLE_TEST_PAYOUTS", raising=False)

        headers = _auth(client, "farmer@test.com")
        resp = client.get("/system/payment-status", headers=headers)
        assert resp.json()["execution_enabled"] is False

    def test_execution_enabled_when_flag_set(self, client, db, farmer_user, monkeypatch):
        monkeypatch.setenv("RAZORPAY_MODE", "test")
        monkeypatch.setenv("RAZORPAY_KEY_ID", "rzp_test_FAKEKEYID")
        monkeypatch.setenv("RAZORPAY_KEY_SECRET", "secret123")
        monkeypatch.setenv("RAZORPAY_ENABLE_TEST_PAYOUTS", "true")

        headers = _auth(client, "farmer@test.com")
        resp = client.get("/system/payment-status", headers=headers)
        assert resp.json()["execution_enabled"] is True

    def test_fpo_can_access_payment_status(self, client, db, fpo_user, fpo_profile, monkeypatch):
        monkeypatch.setenv("RAZORPAY_MODE", "mock")
        headers = _auth(client, "fpo@test.com")
        resp = client.get("/system/payment-status", headers=headers)
        assert resp.status_code == 200


# ── MockPayoutProvider config ──────────────────────────────────────────────────

class TestMockPayoutProviderConfig:
    def test_config_status(self):
        provider = MockPayoutProvider()
        status = provider.get_config_status()
        assert status["provider"] == "mock"
        assert status["configured"] is True
        assert status["execution_enabled"] is True
        assert status["simulated"] is True

    def test_process_payout_returns_success(self):
        provider = MockPayoutProvider()
        req = PayoutRequest(
            payout_id=99,
            idempotency_key="test-idem-99",
            amount_paise=10000,
            currency="INR",
            payout_method="UPI",
            masked_destination="r***@okicici",
            farmer_name="Test Farmer",
        )
        result = provider.process_payout(req)
        assert result.success is True
        assert result.simulated is True
        assert result.provider_reference_id.startswith("MOCK-PAY-99-")


# ── RazorpayXPayoutProvider ───────────────────────────────────────────────────

class TestRazorpayXProvider:
    def test_unconfigured_raises_on_process(self, monkeypatch):
        monkeypatch.delenv("RAZORPAY_KEY_ID", raising=False)
        monkeypatch.delenv("RAZORPAY_KEY_SECRET", raising=False)
        provider = RazorpayXPayoutProvider()
        req = PayoutRequest(
            payout_id=1,
            idempotency_key="idem-1",
            amount_paise=5000,
            currency="INR",
            payout_method="UPI",
            masked_destination="t***@upi",
            farmer_name="Test",
        )
        with pytest.raises(RuntimeError, match="not configured"):
            provider.process_payout(req)

    def test_configured_but_execution_disabled_returns_disabled_message(self, monkeypatch):
        monkeypatch.setenv("RAZORPAY_KEY_ID", "rzp_test_FAKE")
        monkeypatch.setenv("RAZORPAY_KEY_SECRET", "secretval")
        monkeypatch.delenv("RAZORPAY_ENABLE_TEST_PAYOUTS", raising=False)
        provider = RazorpayXPayoutProvider()
        req = PayoutRequest(
            payout_id=2,
            idempotency_key="idem-2",
            amount_paise=5000,
            currency="INR",
            payout_method="UPI",
            masked_destination="t***@upi",
            farmer_name="Test",
        )
        result = provider.process_payout(req)
        assert result.success is False
        assert "disabled" in result.message.lower()
        assert result.provider_reference_id is None
        assert result.simulated is False

    def test_config_status_no_credentials(self, monkeypatch):
        monkeypatch.delenv("RAZORPAY_KEY_ID", raising=False)
        monkeypatch.delenv("RAZORPAY_KEY_SECRET", raising=False)
        provider = RazorpayXPayoutProvider()
        status = provider.get_config_status()
        assert status["configured"] is False
        assert status["key_id_set"] is False
        assert status["secret_set"] is False

    def test_config_status_with_credentials(self, monkeypatch):
        monkeypatch.setenv("RAZORPAY_KEY_ID", "rzp_test_FAKE")
        monkeypatch.setenv("RAZORPAY_KEY_SECRET", "somesecret")
        monkeypatch.setenv("RAZORPAY_ACCOUNT_NUMBER", "12345678901234")
        provider = RazorpayXPayoutProvider()
        status = provider.get_config_status()
        assert status["configured"] is True
        assert status["key_id_set"] is True
        assert status["secret_set"] is True
        assert status["account_number_set"] is True
        # Verify no raw secret value in status dict
        for v in status.values():
            if isinstance(v, str):
                assert "somesecret" not in v, "Secret value exposed in config status!"
                assert "rzp_test_FAKE" not in v, "Key ID value exposed in config status!"

    def test_get_secret_never_stored_as_attribute(self, monkeypatch):
        monkeypatch.setenv("RAZORPAY_KEY_ID", "rzp_test_X")
        monkeypatch.setenv("RAZORPAY_KEY_SECRET", "MY_SECRET_VALUE")
        provider = RazorpayXPayoutProvider()
        # Secret must not be stored as any attribute
        for attr_name in vars(provider):
            attr_val = getattr(provider, attr_name, None)
            if isinstance(attr_val, str):
                assert "MY_SECRET_VALUE" not in attr_val, \
                    f"Secret found in attribute {attr_name}!"


# ── Factory ───────────────────────────────────────────────────────────────────

class TestPayoutProviderFactory:
    def test_default_is_mock(self, monkeypatch):
        monkeypatch.delenv("RAZORPAY_MODE", raising=False)
        assert isinstance(get_payout_provider(), MockPayoutProvider)

    def test_mock_explicit(self, monkeypatch):
        monkeypatch.setenv("RAZORPAY_MODE", "mock")
        assert isinstance(get_payout_provider(), MockPayoutProvider)

    def test_test_mode_returns_razorpayx(self, monkeypatch):
        monkeypatch.setenv("RAZORPAY_MODE", "test")
        assert isinstance(get_payout_provider(), RazorpayXPayoutProvider)

    def test_live_mode_returns_razorpayx(self, monkeypatch):
        monkeypatch.setenv("RAZORPAY_MODE", "live")
        assert isinstance(get_payout_provider(), RazorpayXPayoutProvider)


# ── /credits/my-balance — zero credit certificates ────────────────────────────

class TestCreditBalanceEndpointZeroCerts:
    def test_zero_balance_returns_zeros(self, client, db, farmer_user):
        """No credit balances at all → all zeros."""
        headers = _auth(client, "farmer@test.com")
        resp = client.get("/credits/my-balance", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_earned"] == 0
        assert data["total_available"] == 0
        assert data["total_distributed"] == 0
        assert data["balances"] == []

    def test_certificate_only_balance_shows_zero(self, client, db, farmer_user, fpo_profile):
        """A zero-credit FarmerCreditBalance shows zeros in response."""
        from app.models.farm import Farm, CropCycle
        from app.models.carbon_report import CarbonReport, ReportStatus
        from app.models.farmer_credit_balance import FarmerCreditBalance, CreditBalanceStatus
        from datetime import datetime, timezone

        farm = Farm(
            farmer_id=farmer_user.id, fpo_id=fpo_profile.id,
            farm_name="ZeroFarm", village="V1", district="D1", state="MH",
            land_area_acres=1.0, latitude=18.0, longitude=73.0,
            soil_type="Loamy", water_source="Rain", is_approved=True,
        )
        db.add(farm)
        db.commit()
        db.refresh(farm)

        cycle = CropCycle(
            farm_id=farm.id, crop_type="Rice", season="Kharif",
            start_date=datetime.now(timezone.utc),
            baseline_method="IPCC_TIER1", reduction_practice="SRI",
        )
        db.add(cycle)
        db.commit()
        db.refresh(cycle)

        report = CarbonReport(
            farm_id=farm.id, crop_cycle_id=cycle.id,
            status=ReportStatus.VERIFIED, estimated_credits=0,
            baseline_methane_kg=10.0, current_methane_kg=9.5,
            methane_reduction_kg=0.5, co2e_reduction_tonnes=0.01,
            report_hash="0x" + "b" * 64,
        )
        db.add(report)
        db.commit()
        db.refresh(report)

        balance = FarmerCreditBalance(
            farmer_id=farmer_user.id, fpo_id=fpo_profile.id,
            carbon_report_id=report.id,
            credits_earned=0, credits_available=0, credits_distributed=0,
            status=CreditBalanceStatus.TOKENIZED,
        )
        db.add(balance)
        db.commit()

        headers = _auth(client, "farmer@test.com")
        resp = client.get("/credits/my-balance", headers=headers)
        assert resp.status_code == 200
        data = resp.json()

        assert data["total_earned"] == 0
        assert data["total_available"] == 0
        assert data["total_distributed"] == 0
        assert len(data["balances"]) == 1
        assert data["balances"][0]["credits_earned"] == 0
        assert data["balances"][0]["status"] == "TOKENIZED"

    def test_non_farmer_cannot_access(self, client, db, fpo_user, fpo_profile):
        headers = _auth(client, "fpo@test.com")
        resp = client.get("/credits/my-balance", headers=headers)
        assert resp.status_code == 403
