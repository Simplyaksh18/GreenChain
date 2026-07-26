"""
Phase 9C Mint & Payout Tests.

Covers:
- FPO can mint a verified report linked to their FPO (mock blockchain)
- Minting fails if report not VERIFIED
- Minting fails if farm not linked to FPO
- Minting is blocked if already minted
- Zero-credit report produces DB-only certificate (no real blockchain tx)
- Credit balance is created/updated after mint
- Payout initiation blocked when credits_available == 0
- Payout initiation works when credits_available > 0
- Payout completion updates balance and sets DISTRIBUTED
- Farmer payout details save and update correctly
- FPO can view farmer payout details via /fpo/credits/farmers/{id}/payout-details
- GET /fpo/credits/farmers returns enriched farmer/farm data
"""
import pytest
from app.models.farm import Farm, CropCycle
from app.models.carbon_report import CarbonReport, ReportStatus
from app.models.farmer_profile import FarmerProfile, PayoutMethod
from app.models.farmer_credit_balance import FarmerCreditBalance, CreditBalanceStatus

AUTH = lambda t: {"Authorization": f"Bearer {t}"}


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_verified_report_with_credits(db, farm, cycle, credits=5):
    """Create a VERIFIED report, force estimated_credits to given value."""
    from app.services.carbon_calculator import calculate_carbon_report
    from app.models.sensor import SensorReading
    from app.models.verification import VerificationRequest, VerificationStatus, RiskLevel, Recommendation

    readings = db.query(SensorReading).filter(SensorReading.crop_cycle_id == cycle.id).all()
    if len(readings) < 7:
        from tests.conftest import _make_readings
        readings = _make_readings(db, farm, cycle, count=14)

    calc = calculate_carbon_report(readings, farm.id, cycle.id)
    report = CarbonReport(
        farm_id=farm.id,
        crop_cycle_id=cycle.id,
        baseline_methane_kg=calc.baseline_methane_kg,
        current_methane_kg=calc.current_methane_kg,
        methane_reduction_kg=calc.methane_reduction_kg,
        co2e_reduction_tonnes=calc.co2e_reduction_tonnes,
        estimated_credits=credits,
        report_hash=calc.report_hash,
        status=ReportStatus.VERIFIED,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    vr = VerificationRequest(
        carbon_report_id=report.id,
        status=VerificationStatus.APPROVED,
        risk_score=10.0,
        risk_level=RiskLevel.LOW,
        recommendation=Recommendation.APPROVE,
    )
    db.add(vr)
    db.commit()
    return report


# ── Mint tests ─────────────────────────────────────────────────────────────────

class TestFPOMint:
    def test_fpo_can_mint_verified_linked_report(
        self, client, db, fpo_token, fpo_profile, farm_with_fpo,
    ):
        """FPO mints a verified report on a farm they own."""
        from tests.conftest import _make_cycle, _make_readings
        cycle = _make_cycle(db, farm_with_fpo)
        _make_readings(db, farm_with_fpo, cycle, count=14)
        report = _make_verified_report_with_credits(db, farm_with_fpo, cycle, credits=3)

        resp = client.post(
            f"/fpo/tokens/mint/{report.id}",
            headers=AUTH(fpo_token),
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["credit_amount"] == 3
        assert data["fpo_id"] == fpo_profile.id

    def test_mint_creates_farmer_credit_balance(
        self, client, db, fpo_token, fpo_profile, farm_with_fpo,
    ):
        """After minting, a FarmerCreditBalance row must exist."""
        from tests.conftest import _make_cycle, _make_readings
        cycle = _make_cycle(db, farm_with_fpo)
        _make_readings(db, farm_with_fpo, cycle, count=14)
        report = _make_verified_report_with_credits(db, farm_with_fpo, cycle, credits=4)

        resp = client.post(f"/fpo/tokens/mint/{report.id}", headers=AUTH(fpo_token))
        assert resp.status_code == 201, resp.text

        balance = (
            db.query(FarmerCreditBalance)
            .filter(FarmerCreditBalance.carbon_report_id == report.id)
            .first()
        )
        assert balance is not None
        assert balance.credits_earned == 4
        assert balance.credits_available == 4
        assert balance.credits_distributed == 0
        assert balance.status == CreditBalanceStatus.TOKENIZED

    def test_mint_fails_report_not_verified(
        self, client, db, fpo_token, fpo_profile, farm_with_fpo,
    ):
        """Minting a DRAFT report returns 400 with exact error."""
        from tests.conftest import _make_cycle, _make_readings
        cycle = _make_cycle(db, farm_with_fpo)
        _make_readings(db, farm_with_fpo, cycle, count=14)

        from app.services.carbon_calculator import calculate_carbon_report
        from app.models.sensor import SensorReading
        readings = db.query(SensorReading).filter(SensorReading.crop_cycle_id == cycle.id).all()
        calc = calculate_carbon_report(readings, farm_with_fpo.id, cycle.id)
        report = CarbonReport(
            farm_id=farm_with_fpo.id,
            crop_cycle_id=cycle.id,
            baseline_methane_kg=calc.baseline_methane_kg,
            current_methane_kg=calc.current_methane_kg,
            methane_reduction_kg=calc.methane_reduction_kg,
            co2e_reduction_tonnes=calc.co2e_reduction_tonnes,
            estimated_credits=2,
            report_hash=calc.report_hash,
            status=ReportStatus.DRAFT,
        )
        db.add(report)
        db.commit()
        db.refresh(report)

        resp = client.post(f"/fpo/tokens/mint/{report.id}", headers=AUTH(fpo_token))
        assert resp.status_code == 400
        assert "not verified" in resp.json()["detail"].lower()

    def test_mint_fails_farm_not_linked_to_fpo(
        self, client, db, fpo_token, fpo_profile, farmer_user,
    ):
        """Farm not linked to this FPO → exact 'Farm is not linked' error."""
        from tests.conftest import _make_cycle, _make_readings, _make_farm
        # Explicitly create a farm with NO fpo_id (unlinked)
        unlinked_farm = _make_farm(db, farmer_user, fpo_profile=None, approved=True)
        cycle = _make_cycle(db, unlinked_farm)
        _make_readings(db, unlinked_farm, cycle, count=14)
        report = _make_verified_report_with_credits(db, unlinked_farm, cycle, credits=2)

        resp = client.post(f"/fpo/tokens/mint/{report.id}", headers=AUTH(fpo_token))
        assert resp.status_code == 400
        assert "not linked" in resp.json()["detail"].lower()

    def test_mint_fails_already_minted(
        self, client, db, fpo_token, fpo_profile, farm_with_fpo,
    ):
        """Minting the same report twice → exact 'already minted' error."""
        from tests.conftest import _make_cycle, _make_readings
        cycle = _make_cycle(db, farm_with_fpo)
        _make_readings(db, farm_with_fpo, cycle, count=14)
        report = _make_verified_report_with_credits(db, farm_with_fpo, cycle, credits=2)

        # First mint
        resp1 = client.post(f"/fpo/tokens/mint/{report.id}", headers=AUTH(fpo_token))
        assert resp1.status_code == 201

        # Second mint
        resp2 = client.post(f"/fpo/tokens/mint/{report.id}", headers=AUTH(fpo_token))
        assert resp2.status_code == 400
        detail = resp2.json()["detail"].lower()
        assert "already minted" in detail or "token already minted" in detail

    def test_mint_zero_credit_report_issues_certificate(
        self, client, db, fpo_token, fpo_profile, farm_with_fpo,
    ):
        """Zero-credit report (below 1 tCO₂e threshold) → DB-only certificate."""
        from tests.conftest import _make_cycle, _make_readings
        cycle = _make_cycle(db, farm_with_fpo)
        _make_readings(db, farm_with_fpo, cycle, count=14)
        report = _make_verified_report_with_credits(db, farm_with_fpo, cycle, credits=0)

        resp = client.post(f"/fpo/tokens/mint/{report.id}", headers=AUTH(fpo_token))
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["credit_amount"] == 0

        # Credit balance should exist with zero credits
        balance = (
            db.query(FarmerCreditBalance)
            .filter(FarmerCreditBalance.carbon_report_id == report.id)
            .first()
        )
        assert balance is not None
        assert balance.credits_earned == 0
        assert balance.credits_available == 0

    def test_non_fpo_cannot_use_fpo_mint(
        self, client, db, farmer_token, farm_with_fpo,
    ):
        """FARMER cannot call FPO mint endpoint."""
        resp = client.post("/fpo/tokens/mint/999", headers=AUTH(farmer_token))
        assert resp.status_code == 403


# ── FPO Credits (enriched) ─────────────────────────────────────────────────────

class TestFPOCreditsEnriched:
    def test_fpo_credits_farmers_returns_enriched_data(
        self, client, db, fpo_token, fpo_profile, farm_with_fpo, farmer_user,
    ):
        """GET /fpo/credits/farmers returns farmer_name, farm_name fields."""
        from tests.conftest import _make_cycle, _make_readings
        cycle = _make_cycle(db, farm_with_fpo)
        _make_readings(db, farm_with_fpo, cycle, count=14)
        report = _make_verified_report_with_credits(db, farm_with_fpo, cycle, credits=2)

        # Mint to create a balance
        client.post(f"/fpo/tokens/mint/{report.id}", headers=AUTH(fpo_token))

        resp = client.get("/fpo/credits/farmers", headers=AUTH(fpo_token))
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1

        balance = next((b for b in data if b["carbon_report_id"] == report.id), None)
        assert balance is not None
        assert balance["farmer_name"] == farmer_user.name
        assert balance["farm_name"] == farm_with_fpo.farm_name
        assert "farmer_email" in balance

    def test_fpo_payout_details_endpoint(
        self, client, db, fpo_token, fpo_profile, farm_with_fpo, farmer_user,
    ):
        """FPO can view farmer payout details for a balance."""
        from tests.conftest import _make_cycle, _make_readings

        # Set up farmer payout details
        profile = FarmerProfile(
            user_id=farmer_user.id,
            preferred_payout_method=PayoutMethod.UPI,
            upi_id="farmertest@upi",
        )
        db.add(profile)
        db.commit()

        cycle = _make_cycle(db, farm_with_fpo)
        _make_readings(db, farm_with_fpo, cycle, count=14)
        report = _make_verified_report_with_credits(db, farm_with_fpo, cycle, credits=2)
        client.post(f"/fpo/tokens/mint/{report.id}", headers=AUTH(fpo_token))

        balance = (
            db.query(FarmerCreditBalance)
            .filter(FarmerCreditBalance.carbon_report_id == report.id)
            .first()
        )
        assert balance is not None

        resp = client.get(
            f"/fpo/credits/farmers/{balance.id}/payout-details",
            headers=AUTH(fpo_token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["preferred_payout_method"] == "UPI"
        # Phase 10A: FPO sees masked UPI only (never raw)
        assert data.get("upi_id_masked") == "f***@upi"
        assert "farmertest@upi" not in str(data)
        assert data["has_payout_details"] is True


# ── Payout tests ───────────────────────────────────────────────────────────────

class TestPayouts:
    def _setup_balance(self, client, db, fpo_token, fpo_profile, farm_with_fpo):
        """Helper: mint a report to create a credit balance, return balance."""
        from tests.conftest import _make_cycle, _make_readings
        cycle = _make_cycle(db, farm_with_fpo)
        _make_readings(db, farm_with_fpo, cycle, count=14)
        report = _make_verified_report_with_credits(db, farm_with_fpo, cycle, credits=10)
        resp = client.post(f"/fpo/tokens/mint/{report.id}", headers=AUTH(fpo_token))
        assert resp.status_code == 201
        balance = (
            db.query(FarmerCreditBalance)
            .filter(FarmerCreditBalance.carbon_report_id == report.id)
            .first()
        )
        assert balance is not None
        return balance

    def test_initiate_payout_works_with_available_credits(
        self, client, db, fpo_token, fpo_profile, farm_with_fpo,
    ):
        """FPO can initiate a payout when credits_available > 0."""
        balance = self._setup_balance(client, db, fpo_token, fpo_profile, farm_with_fpo)

        resp = client.post(
            "/fpo/payouts/initiate",
            json={
                "credit_balance_id": balance.id,
                "amount_credits": 5,
                "price_per_credit": 500,
                "currency": "INR",
                "remarks": "First partial payout",
            },
            headers=AUTH(fpo_token),
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["amount_credits"] == 5
        assert data["payout_amount"] == 2500.0
        assert data["status"] == "INITIATED"

    def test_initiate_payout_blocked_when_zero_available(
        self, client, db, fpo_token, fpo_profile, farm_with_fpo,
    ):
        """FPO cannot initiate payout when credits_available is 0."""
        from tests.conftest import _make_cycle, _make_readings
        cycle = _make_cycle(db, farm_with_fpo)
        _make_readings(db, farm_with_fpo, cycle, count=14)
        report = _make_verified_report_with_credits(db, farm_with_fpo, cycle, credits=0)
        client.post(f"/fpo/tokens/mint/{report.id}", headers=AUTH(fpo_token))
        balance = (
            db.query(FarmerCreditBalance)
            .filter(FarmerCreditBalance.carbon_report_id == report.id)
            .first()
        )

        resp = client.post(
            "/fpo/payouts/initiate",
            json={
                "credit_balance_id": balance.id,
                "amount_credits": 1,
                "price_per_credit": 500,
                "currency": "INR",
            },
            headers=AUTH(fpo_token),
        )
        assert resp.status_code == 400
        assert "insufficient" in resp.json()["detail"].lower()

    def test_complete_payout_updates_balance(
        self, client, db, fpo_token, fpo_profile, farm_with_fpo,
    ):
        """Completing a payout correctly updates credits_distributed and credits_available."""
        balance = self._setup_balance(client, db, fpo_token, fpo_profile, farm_with_fpo)

        # Initiate
        resp1 = client.post(
            "/fpo/payouts/initiate",
            json={
                "credit_balance_id": balance.id,
                "amount_credits": 10,
                "price_per_credit": 600,
                "currency": "INR",
            },
            headers=AUTH(fpo_token),
        )
        assert resp1.status_code == 201
        payout_id = resp1.json()["id"]

        # Complete
        resp2 = client.post(
            f"/fpo/payouts/{payout_id}/complete",
            json={"remarks": "Transferred via UPI"},
            headers=AUTH(fpo_token),
        )
        assert resp2.status_code == 200
        assert resp2.json()["status"] == "COMPLETED"

        # Balance should be DISTRIBUTED
        db.expire(balance)
        db.refresh(balance)
        assert balance.credits_distributed == 10
        assert balance.credits_available == 0
        assert balance.status == CreditBalanceStatus.DISTRIBUTED


# ── Farmer payout details ──────────────────────────────────────────────────────

class TestFarmerPayoutDetails:
    def test_farmer_can_save_upi_details(self, client, db, farmer_token, farmer_user):
        """POST /farmers/payout-details saves UPI info."""
        resp = client.post(
            "/farmers/payout-details",
            json={
                "preferred_payout_method": "UPI",
                "upi_id": "test@okaxis",
            },
            headers=AUTH(farmer_token),
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["preferred_payout_method"] == "UPI"
        # Phase 10A: raw upi_id replaced by upi_id_masked
        assert data.get("upi_id_masked") == "t***@okaxis"

    def test_farmer_can_save_bank_details(self, client, db, farmer_token, farmer_user):
        """POST /farmers/payout-details saves bank account info (masked in response)."""
        resp = client.post(
            "/farmers/payout-details",
            json={
                "preferred_payout_method": "BANK_TRANSFER",
                "bank_account_holder_name": "Alice Farmer",
                "bank_account_number": "123456789012",
                "ifsc_code": "SBIN0001234",
            },
            headers=AUTH(farmer_token),
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["preferred_payout_method"] == "BANK_TRANSFER"
        # Account number must be masked (not plain text)
        masked = data.get("bank_account_number_masked")
        assert masked is not None
        assert "123456789012" not in (masked or "")
        assert data["ifsc_code"] == "SBIN0001234"

    def test_farmer_can_update_payout_details(self, client, db, farmer_token, farmer_user):
        """POST /farmers/payout-details twice → upsert."""
        client.post(
            "/farmers/payout-details",
            json={"preferred_payout_method": "UPI", "upi_id": "old@upi"},
            headers=AUTH(farmer_token),
        )
        resp = client.post(
            "/farmers/payout-details",
            json={"preferred_payout_method": "UPI", "upi_id": "new@paytm"},
            headers=AUTH(farmer_token),
        )
        assert resp.status_code == 200
        assert resp.json()["upi_id_masked"] == "n***@paytm"

    def test_farmer_can_get_own_payout_details(self, client, db, farmer_token, farmer_user):
        """GET /farmers/payout-details returns previously saved details."""
        client.post(
            "/farmers/payout-details",
            json={"preferred_payout_method": "UPI", "upi_id": "read@upi"},
            headers=AUTH(farmer_token),
        )
        resp = client.get("/farmers/payout-details", headers=AUTH(farmer_token))
        assert resp.status_code == 200
        assert resp.json()["upi_id_masked"] == "r***@upi"

    def test_invalid_ifsc_rejected(self, client, farmer_token):
        """IFSC must be exactly 11 characters."""
        resp = client.post(
            "/farmers/payout-details",
            json={
                "preferred_payout_method": "BANK_TRANSFER",
                "bank_account_holder_name": "Test",
                "bank_account_number": "123456789",
                "ifsc_code": "SHORT",
            },
            headers=AUTH(farmer_token),
        )
        assert resp.status_code == 422
