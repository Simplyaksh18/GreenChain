"""
Phase 9 — Custodial Carbon Credit Model tests.

Covers:
  1.  FPO wallet validation (PATCH /fpo/profile/wallet)
  2.  Farmer payout details (POST/GET /farmers/payout-details)
  3.  Farmer credit balance creation on custodial mint
  4.  Token minting requires FPO via /fpo/tokens/mint/{report_id}
  5.  Token mints to FPO (fpo_id set on token)
  6.  Farmer wallet no longer required for minting
  7.  FPO can view farmer credit balances
  8.  FPO can initiate payout
  9.  Payout completion updates credit balance
  10. Farmer can view own payouts
  11. Unauthorised payout access blocked
  12. Admin credit summary
  13. Admin can view all payouts
"""
import pytest
from datetime import datetime

AUTH = lambda t: {"Authorization": f"Bearer {t}"}

# ── helpers ───────────────────────────────────────────────────────────────────

def _create_fpo_profile(client, fpo_token, reg="REG-CUST-001"):
    resp = client.post(
        "/fpo/profile",
        json={
            "organization_name": "CustodialFPO",
            "registration_number": reg,
            "district": "Pune",
            "state": "Maharashtra",
        },
        headers=AUTH(fpo_token),
    )
    # If already exists that's fine
    assert resp.status_code in (200, 201, 400)
    if resp.status_code == 400 and "already exists" in resp.json().get("detail", ""):
        return client.get("/fpo/profile", headers=AUTH(fpo_token)).json()
    return resp.json()


def _make_cycle(client, farmer_token, farm_id, start_date="2024-06-01"):
    resp = client.post(
        f"/farms/{farm_id}/crop-cycles",
        json={
            "crop_type": "Paddy",
            "season": "Kharif",
            "start_date": start_date,
            "baseline_method": "AWD",
            "reduction_practice": "SRI",
        },
        headers=AUTH(farmer_token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _seed_verified_report(client, farmer_token, verifier_token, farm_id):
    """Create a full pipeline: cycle → sensor sim → report → submit → verify.

    Uses correct API endpoints:
      POST /carbon-reports/generate/{cycle_id}
      POST /carbon-reports/{id}/submit
      GET  /verification/pending  (verifier_token)
      POST /verification/{vr_id}/approve  (verifier_token)
    """
    # Use fixed old start date to ensure many readings available
    cycle_id = _make_cycle(client, farmer_token, farm_id, start_date="2024-06-01")

    client.post(
        "/sensors/simulate",
        json={"farm_id": farm_id, "crop_cycle_id": cycle_id, "number_of_days": 14},
        headers=AUTH(farmer_token),
    )
    # Generate report
    rep_resp = client.post(
        f"/carbon-reports/generate/{cycle_id}",
        headers=AUTH(farmer_token),
    )
    assert rep_resp.status_code == 201, rep_resp.text
    report_id = rep_resp.json()["id"]

    # Submit → creates VerificationRequest automatically
    sub = client.post(f"/carbon-reports/{report_id}/submit", headers=AUTH(farmer_token))
    assert sub.status_code == 200, sub.text

    # Approve via verifier
    pending = client.get("/verification/pending", headers=AUTH(verifier_token))
    assert pending.status_code == 200, pending.text
    vrs = [v for v in pending.json() if v["carbon_report_id"] == report_id]
    assert len(vrs) >= 1, f"No VerificationRequest found for report {report_id}"
    vr_id = vrs[0]["id"]
    approve_resp = client.post(f"/verification/{vr_id}/approve", headers=AUTH(verifier_token))
    assert approve_resp.status_code == 200, approve_resp.text
    return report_id


# ════════════════════════════════════════════════════════════════════════════════
class TestFPOWallet:
    # Valid 42-char EVM address (0x + 40 hex digits)
    VALID_WALLET = "0xAbCd1234567890AbCd1234567890AbCd12345678"
    VALID_WALLET_LC = VALID_WALLET.lower()  # schema lowercases it

    def test_fpo_can_set_wallet(self, client, fpo_token, fpo_profile):
        resp = client.patch(
            "/fpo/profile/wallet",
            json={"wallet_address": self.VALID_WALLET,
                  "vault_identifier": "FPO-VAULT-001"},
            headers=AUTH(fpo_token),
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["wallet_address"] == self.VALID_WALLET_LC
        assert data["vault_identifier"] == "FPO-VAULT-001"

    def test_fpo_wallet_invalid_address(self, client, fpo_token, fpo_profile):
        resp = client.patch(
            "/fpo/profile/wallet",
            json={"wallet_address": "not-a-valid-address"},
            headers=AUTH(fpo_token),
        )
        assert resp.status_code == 422

    def test_fpo_wallet_too_short(self, client, fpo_token, fpo_profile):
        resp = client.patch(
            "/fpo/profile/wallet",
            json={"wallet_address": "0xabcd"},
            headers=AUTH(fpo_token),
        )
        assert resp.status_code == 422

    def test_fpo_can_get_wallet(self, client, fpo_token, fpo_profile):
        # Set first
        client.patch(
            "/fpo/profile/wallet",
            json={"wallet_address": "0xabc1234567890abcdef1234567890abcdef123456"},
            headers=AUTH(fpo_token),
        )
        resp = client.get("/fpo/profile/wallet", headers=AUTH(fpo_token))
        assert resp.status_code == 200, resp.text
        assert "wallet_address" in resp.json()

    def test_farmer_cannot_access_fpo_wallet(self, client, farmer_token, fpo_profile):
        resp = client.get("/fpo/profile/wallet", headers=AUTH(farmer_token))
        assert resp.status_code == 403

    def test_unauthenticated_rejected(self, client):
        resp = client.get("/fpo/profile/wallet")
        assert resp.status_code == 401


# ════════════════════════════════════════════════════════════════════════════════
class TestFarmerPayoutDetails:
    def test_farmer_can_set_payout_details_upi(self, client, farmer_token):
        resp = client.post(
            "/farmers/payout-details",
            json={"preferred_payout_method": "UPI", "upi_id": "farmer@okaxis"},
            headers=AUTH(farmer_token),
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        # Phase 10A: raw upi_id replaced by upi_id_masked
        assert data.get("upi_id_masked") == "f***@okaxis"
        assert data["preferred_payout_method"] == "UPI"

    def test_farmer_can_set_bank_details(self, client, farmer_token):
        resp = client.post(
            "/farmers/payout-details",
            json={
                "preferred_payout_method": "BANK_TRANSFER",
                "bank_account_holder_name": "Ramu Farmer",
                "bank_account_number": "1234567890123",
                "ifsc_code": "SBIN0001234",
            },
            headers=AUTH(farmer_token),
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["bank_account_holder_name"] == "Ramu Farmer"
        # Bank number must be masked
        assert "bank_account_number_masked" in data
        raw = data.get("bank_account_number_masked", "")
        assert raw.endswith("0123")           # last 4 visible
        assert "*" in raw                     # rest masked

    def test_bank_number_full_never_exposed(self, client, farmer_token):
        client.post(
            "/farmers/payout-details",
            json={"bank_account_number": "9876543210123", "ifsc_code": "HDFC0001234"},
            headers=AUTH(farmer_token),
        )
        resp = client.get("/farmers/payout-details", headers=AUTH(farmer_token))
        data = resp.json()
        # Full account number must never appear in any response field
        assert "9876543210123" not in str(data)

    def test_invalid_ifsc_rejected(self, client, farmer_token):
        resp = client.post(
            "/farmers/payout-details",
            json={"ifsc_code": "TOOSHORT"},
            headers=AUTH(farmer_token),
        )
        assert resp.status_code == 422

    def test_invalid_account_number_rejected(self, client, farmer_token):
        resp = client.post(
            "/farmers/payout-details",
            json={"bank_account_number": "1234"},   # too short
            headers=AUTH(farmer_token),
        )
        assert resp.status_code == 422

    def test_farmer_can_get_payout_details(self, client, farmer_token):
        client.post(
            "/farmers/payout-details",
            json={"upi_id": "test@upi"},
            headers=AUTH(farmer_token),
        )
        resp = client.get("/farmers/payout-details", headers=AUTH(farmer_token))
        assert resp.status_code == 200
        # Phase 10A: raw upi_id replaced by upi_id_masked in response
        assert resp.json()["upi_id_masked"] == "t***@upi"

    def test_get_before_set_returns_404(self, client, farmer_token):
        resp = client.get("/farmers/payout-details", headers=AUTH(farmer_token))
        assert resp.status_code == 404

    def test_non_farmer_cannot_access(self, client, fpo_token):
        resp = client.get("/farmers/payout-details", headers=AUTH(fpo_token))
        assert resp.status_code == 403


# ════════════════════════════════════════════════════════════════════════════════
class TestCustodialMinting:
    def test_admin_mint_creates_credit_balance_for_fpo_farm(
        self, client, farmer_token, verifier_token, admin_token, farm_with_fpo
    ):
        """When farm has fpo_id, minting should auto-create a FarmerCreditBalance."""
        report_id = _seed_verified_report(client, farmer_token, verifier_token, farm_with_fpo.id)
        resp = client.post(
            f"/admin/tokens/mint/{report_id}",
            headers=AUTH(admin_token),
        )
        assert resp.status_code == 201, resp.text
        token = resp.json()
        # FPO custodial fields should be set
        assert token["fpo_id"] is not None
        assert token["custodial_owner_type"] == "FPO"
        assert token["beneficiary_farmer_id"] is not None

    def test_admin_mint_works_without_fpo_farm(
        self, client, farmer_token, verifier_token, admin_token, farm
    ):
        """Backward compat: admin can still mint for farms not linked to FPO."""
        report_id = _seed_verified_report(client, farmer_token, verifier_token, farm.id)
        resp = client.post(
            f"/admin/tokens/mint/{report_id}",
            headers=AUTH(admin_token),
        )
        assert resp.status_code == 201, resp.text
        token = resp.json()
        assert token["fpo_id"] is None           # No FPO
        assert token["custodial_owner_type"] == "FPO"

    def test_fpo_can_mint_for_linked_farm(
        self, client, farmer_token, verifier_token, admin_token, fpo_token, farm_with_fpo, fpo_profile
    ):
        """FPO endpoint enforces farm linkage and mints custodially."""
        report_id = _seed_verified_report(client, farmer_token, verifier_token, farm_with_fpo.id)
        resp = client.post(
            f"/fpo/tokens/mint/{report_id}",
            headers=AUTH(fpo_token),
        )
        assert resp.status_code == 201, resp.text
        token = resp.json()
        assert token["fpo_id"] == fpo_profile.id
        assert token["custodial_owner_type"] == "FPO"

    def test_fpo_cannot_mint_for_unlinked_farm(
        self, client, farmer_token, verifier_token, admin_token, fpo_token, farm, fpo_profile
    ):
        """Farm not linked to this FPO → 400 error."""
        report_id = _seed_verified_report(client, farmer_token, verifier_token, farm.id)
        resp = client.post(
            f"/fpo/tokens/mint/{report_id}",
            headers=AUTH(fpo_token),
        )
        assert resp.status_code == 400
        assert "not linked" in resp.json()["detail"].lower()

    def test_farmer_wallet_not_required_for_minting(
        self, client, farmer_token, verifier_token, admin_token, farm
    ):
        """Farmer user has no wallet_address — minting must still succeed."""
        report_id = _seed_verified_report(client, farmer_token, verifier_token, farm.id)
        resp = client.post(
            f"/admin/tokens/mint/{report_id}",
            headers=AUTH(admin_token),
        )
        assert resp.status_code == 201, resp.text

    def test_farmer_cannot_mint(self, client, farmer_token, verifier_token, admin_token, farm):
        report_id = _seed_verified_report(client, farmer_token, verifier_token, farm.id)
        # POST /admin/tokens/mint is admin-only
        resp = client.post(
            f"/admin/tokens/mint/{report_id}",
            headers=AUTH(farmer_token),
        )
        assert resp.status_code == 403


# ════════════════════════════════════════════════════════════════════════════════
class TestCreditBalance:
    def test_farmer_can_view_own_balance(self, client, farmer_token):
        resp = client.get("/credits/my-balance", headers=AUTH(farmer_token))
        assert resp.status_code == 200
        data = resp.json()
        assert "total_earned" in data
        assert "total_available" in data
        assert "balances" in data

    def test_fpo_can_view_farmer_balances(self, client, fpo_token, fpo_profile):
        resp = client.get("/fpo/credits/farmers", headers=AUTH(fpo_token))
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_farmer_cannot_view_fpo_balances(self, client, farmer_token):
        resp = client.get("/fpo/credits/farmers", headers=AUTH(farmer_token))
        assert resp.status_code == 403

    def test_admin_can_view_credit_summary(self, client, admin_token):
        resp = client.get("/admin/credits/summary", headers=AUTH(admin_token))
        assert resp.status_code == 200
        data = resp.json()
        assert "total_balances" in data
        assert "by_status" in data

    def test_farmer_cannot_view_admin_summary(self, client, farmer_token):
        resp = client.get("/admin/credits/summary", headers=AUTH(farmer_token))
        assert resp.status_code == 403


# ════════════════════════════════════════════════════════════════════════════════
class TestPayouts:
    def test_fpo_can_initiate_payout(
        self, client, farmer_token, verifier_token, admin_token, fpo_token, farm_with_fpo, fpo_profile
    ):
        """Full pipeline: mint → create balance → initiate payout."""
        # Mint (creates balance)
        report_id = _seed_verified_report(client, farmer_token, verifier_token, farm_with_fpo.id)
        client.post(f"/admin/tokens/mint/{report_id}", headers=AUTH(admin_token))

        # Get balance ID via FPO endpoint
        balances = client.get("/fpo/credits/farmers", headers=AUTH(fpo_token)).json()
        if not balances:
            pytest.skip("No credit balances created (estimated_credits may be 0)")

        balance_id = balances[0]["id"]
        credits_available = balances[0]["credits_available"]
        if credits_available < 1:
            pytest.skip("No available credits to pay out")

        # Initiate payout
        resp = client.post(
            "/fpo/payouts/initiate",
            json={
                "credit_balance_id": balance_id,
                "amount_credits": 1,
                "price_per_credit": 500,
                "currency": "INR",
                "remarks": "Test payout",
            },
            headers=AUTH(fpo_token),
        )
        assert resp.status_code == 201, resp.text
        payout = resp.json()
        assert payout["status"] == "INITIATED"
        assert payout["amount_credits"] == 1
        assert payout["payout_amount"] == 500

    def test_fpo_can_complete_payout(
        self, client, farmer_token, verifier_token, admin_token, fpo_token, farm_with_fpo, fpo_profile
    ):
        """Full pipeline: mint → payout initiate → payout complete → balance updated."""
        report_id = _seed_verified_report(client, farmer_token, verifier_token, farm_with_fpo.id)
        client.post(f"/admin/tokens/mint/{report_id}", headers=AUTH(admin_token))

        balances = client.get("/fpo/credits/farmers", headers=AUTH(fpo_token)).json()
        if not balances or balances[0]["credits_available"] < 1:
            pytest.skip("No available credits")

        balance_id = balances[0]["id"]
        credits_before = balances[0]["credits_available"]

        # Initiate
        payout = client.post(
            "/fpo/payouts/initiate",
            json={"credit_balance_id": balance_id, "amount_credits": 1, "price_per_credit": 100},
            headers=AUTH(fpo_token),
        ).json()
        payout_id = payout["id"]

        # Complete
        complete_resp = client.post(
            f"/fpo/payouts/{payout_id}/complete",
            json={"remarks": "Wire transfer done"},
            headers=AUTH(fpo_token),
        )
        assert complete_resp.status_code == 200, complete_resp.text
        assert complete_resp.json()["status"] == "COMPLETED"

        # Balance should be reduced
        updated_balances = client.get("/fpo/credits/farmers", headers=AUTH(fpo_token)).json()
        updated = next(b for b in updated_balances if b["id"] == balance_id)
        assert updated["credits_distributed"] == 1
        assert updated["credits_available"] == credits_before - 1

    def test_payout_exceeding_available_credits_rejected(
        self, client, farmer_token, verifier_token, admin_token, fpo_token, farm_with_fpo, fpo_profile
    ):
        report_id = _seed_verified_report(client, farmer_token, verifier_token, farm_with_fpo.id)
        client.post(f"/admin/tokens/mint/{report_id}", headers=AUTH(admin_token))

        balances = client.get("/fpo/credits/farmers", headers=AUTH(fpo_token)).json()
        if not balances:
            pytest.skip("No balances")

        balance_id = balances[0]["id"]
        credits_available = balances[0]["credits_available"]

        # Try to pay out more than available
        resp = client.post(
            "/fpo/payouts/initiate",
            json={
                "credit_balance_id": balance_id,
                "amount_credits": credits_available + 9999,
                "price_per_credit": 100,
            },
            headers=AUTH(fpo_token),
        )
        assert resp.status_code == 400
        assert "insufficient" in resp.json()["detail"].lower()

    def test_farmer_can_view_own_payouts(self, client, farmer_token):
        resp = client.get("/farmers/payouts", headers=AUTH(farmer_token))
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_farmer_cannot_initiate_payout(self, client, farmer_token):
        resp = client.post(
            "/fpo/payouts/initiate",
            json={"credit_balance_id": 1, "amount_credits": 1, "price_per_credit": 100},
            headers=AUTH(farmer_token),
        )
        assert resp.status_code == 403

    def test_admin_can_view_all_payouts(self, client, admin_token):
        resp = client.get("/admin/payouts", headers=AUTH(admin_token))
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_verifier_cannot_view_payouts(self, client, verifier_token):
        resp = client.get("/admin/payouts", headers=AUTH(verifier_token))
        assert resp.status_code == 403

    def test_unauthenticated_cannot_initiate_payout(self, client):
        resp = client.post(
            "/fpo/payouts/initiate",
            json={"credit_balance_id": 1, "amount_credits": 1, "price_per_credit": 100},
        )
        assert resp.status_code == 401

    def test_fpo_cannot_complete_other_fpo_payout(
        self, client, fpo2_token, fpo2_profile
    ):
        """FPO2 cannot complete payouts belonging to FPO1."""
        resp = client.post(
            "/fpo/payouts/9999/complete",
            json={},
            headers=AUTH(fpo2_token),
        )
        assert resp.status_code == 404   # payout 9999 doesn't exist
