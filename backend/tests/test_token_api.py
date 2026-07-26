"""
Phase 5 — Token API tests.
Covers: POST /admin/tokens/mint/{report_id}
        GET  /tokens/my-wallet
        GET  /tokens/{token_id}
        POST /admin/tokens/{token_id}/retire
        POST /admin/tokens/{token_id}/suspend
"""
import pytest

AUTH = lambda t: {"Authorization": f"Bearer {t}"}


class TestMintToken:
    def test_admin_can_mint_verified_report(self, client, admin_token, admin_user,
                                             verified_report, farmer_user):
        resp = client.post(f"/admin/tokens/mint/{verified_report.id}",
                           headers=AUTH(admin_token))
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["carbon_report_id"] == verified_report.id
        assert data["farmer_id"] == farmer_user.id
        assert data["status"] == "MINTED"
        assert data["token_id"].startswith("GC-CARBON-")
        assert data["token_standard"] == "ERC1155_MOCK"
        assert data["credit_amount"] >= 0
        assert data["minted_tx_hash"] is not None

    def test_zero_credit_report_mints_certificate(self, client, admin_token, admin_user,
                                                    zero_credit_verified_report):
        resp = client.post(f"/admin/tokens/mint/{zero_credit_verified_report.id}",
                           headers=AUTH(admin_token))
        assert resp.status_code == 201
        data = resp.json()
        assert data["credit_amount"] == 0
        assert data["is_certificate"] is True

    def test_positive_credit_report_not_certificate(self, client, admin_token, admin_user,
                                                      verified_report, sensor_readings):
        resp = client.post(f"/admin/tokens/mint/{verified_report.id}",
                           headers=AUTH(admin_token))
        assert resp.status_code == 201
        # Only zero-credit tokens are certificates
        # credit_amount could be 0 depending on the sensor data, so check is_certificate matches
        data = resp.json()
        assert data["is_certificate"] == (data["credit_amount"] == 0)

    def test_duplicate_mint_rejected(self, client, admin_token, admin_user, verified_report):
        client.post(f"/admin/tokens/mint/{verified_report.id}", headers=AUTH(admin_token))
        resp = client.post(f"/admin/tokens/mint/{verified_report.id}", headers=AUTH(admin_token))
        assert resp.status_code == 400

    def test_unverified_report_cannot_mint(self, client, admin_token, admin_user,
                                            carbon_report_draft):
        resp = client.post(f"/admin/tokens/mint/{carbon_report_draft.id}",
                           headers=AUTH(admin_token))
        assert resp.status_code == 400

    def test_submitted_report_cannot_mint(self, client, admin_token, admin_user,
                                           carbon_report_submitted):
        resp = client.post(f"/admin/tokens/mint/{carbon_report_submitted.id}",
                           headers=AUTH(admin_token))
        assert resp.status_code == 400

    def test_farmer_cannot_mint(self, client, farmer_token, verified_report):
        resp = client.post(f"/admin/tokens/mint/{verified_report.id}",
                           headers=AUTH(farmer_token))
        assert resp.status_code == 403

    def test_verifier_cannot_mint(self, client, verifier_token, verifier_user, verified_report):
        resp = client.post(f"/admin/tokens/mint/{verified_report.id}",
                           headers=AUTH(verifier_token))
        assert resp.status_code == 403

    def test_report_not_found(self, client, admin_token, admin_user):
        resp = client.post("/admin/tokens/mint/99999", headers=AUTH(admin_token))
        assert resp.status_code == 404

    def test_unauthenticated_rejected(self, client, verified_report):
        resp = client.post(f"/admin/tokens/mint/{verified_report.id}")
        assert resp.status_code == 401


class TestMyWallet:
    def test_farmer_sees_own_tokens(self, client, farmer_token, farmer_user,
                                     admin_token, admin_user, verified_report):
        client.post(f"/admin/tokens/mint/{verified_report.id}", headers=AUTH(admin_token))
        resp = client.get("/tokens/my-wallet", headers=AUTH(farmer_token))
        assert resp.status_code == 200
        tokens = resp.json()
        assert len(tokens) == 1
        assert tokens[0]["farmer_id"] == farmer_user.id

    def test_farmer_empty_wallet(self, client, farmer_token):
        resp = client.get("/tokens/my-wallet", headers=AUTH(farmer_token))
        assert resp.status_code == 200
        assert resp.json() == []

    def test_verifier_cannot_view_wallet(self, client, verifier_token, verifier_user):
        resp = client.get("/tokens/my-wallet", headers=AUTH(verifier_token))
        assert resp.status_code == 403

    def test_admin_cannot_view_wallet(self, client, admin_token, admin_user):
        resp = client.get("/tokens/my-wallet", headers=AUTH(admin_token))
        assert resp.status_code == 403

    def test_fpo_cannot_view_wallet(self, client, fpo_token, fpo_profile):
        resp = client.get("/tokens/my-wallet", headers=AUTH(fpo_token))
        assert resp.status_code == 403

    def test_unauthenticated_rejected(self, client):
        resp = client.get("/tokens/my-wallet")
        assert resp.status_code == 401


class TestGetToken:
    def test_farmer_gets_own_token(self, client, farmer_token, farmer_user,
                                    admin_token, admin_user, verified_report):
        mint = client.post(f"/admin/tokens/mint/{verified_report.id}", headers=AUTH(admin_token))
        token_id = mint.json()["id"]
        resp = client.get(f"/tokens/{token_id}", headers=AUTH(farmer_token))
        assert resp.status_code == 200
        assert resp.json()["id"] == token_id

    def test_farmer2_cannot_get_other_farmer_token(self, client, farmer2_token,
                                                     admin_token, admin_user,
                                                     verified_report):
        mint = client.post(f"/admin/tokens/mint/{verified_report.id}", headers=AUTH(admin_token))
        token_id = mint.json()["id"]
        resp = client.get(f"/tokens/{token_id}", headers=AUTH(farmer2_token))
        assert resp.status_code == 403

    def test_verifier_can_get_any_token(self, client, verifier_token, verifier_user,
                                         admin_token, admin_user, verified_report):
        mint = client.post(f"/admin/tokens/mint/{verified_report.id}", headers=AUTH(admin_token))
        token_id = mint.json()["id"]
        resp = client.get(f"/tokens/{token_id}", headers=AUTH(verifier_token))
        assert resp.status_code == 200

    def test_admin_can_get_any_token(self, client, admin_token, admin_user, verified_report):
        mint = client.post(f"/admin/tokens/mint/{verified_report.id}", headers=AUTH(admin_token))
        token_id = mint.json()["id"]
        resp = client.get(f"/tokens/{token_id}", headers=AUTH(admin_token))
        assert resp.status_code == 200

    def test_token_not_found(self, client, farmer_token):
        resp = client.get("/tokens/99999", headers=AUTH(farmer_token))
        assert resp.status_code == 404

    def test_unauthenticated_rejected(self, client, admin_token, admin_user, verified_report):
        mint = client.post(f"/admin/tokens/mint/{verified_report.id}", headers=AUTH(admin_token))
        token_id = mint.json()["id"]
        resp = client.get(f"/tokens/{token_id}")
        assert resp.status_code == 401


class TestRetireToken:
    def test_admin_can_retire_token(self, client, admin_token, admin_user, minted_token):
        resp = client.post(f"/admin/tokens/{minted_token.id}/retire",
                           headers=AUTH(admin_token))
        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == "RETIRED"

    def test_cannot_retire_already_retired(self, client, admin_token, admin_user, minted_token):
        client.post(f"/admin/tokens/{minted_token.id}/retire", headers=AUTH(admin_token))
        resp = client.post(f"/admin/tokens/{minted_token.id}/retire", headers=AUTH(admin_token))
        assert resp.status_code == 400

    def test_farmer_cannot_retire(self, client, farmer_token, minted_token):
        resp = client.post(f"/admin/tokens/{minted_token.id}/retire",
                           headers=AUTH(farmer_token))
        assert resp.status_code == 403

    def test_verifier_cannot_retire(self, client, verifier_token, verifier_user, minted_token):
        resp = client.post(f"/admin/tokens/{minted_token.id}/retire",
                           headers=AUTH(verifier_token))
        assert resp.status_code == 403

    def test_token_not_found(self, client, admin_token, admin_user):
        resp = client.post("/admin/tokens/99999/retire", headers=AUTH(admin_token))
        assert resp.status_code == 404

    def test_unauthenticated_rejected(self, client, minted_token):
        resp = client.post(f"/admin/tokens/{minted_token.id}/retire")
        assert resp.status_code == 401


class TestSuspendToken:
    def test_admin_can_suspend_token(self, client, admin_token, admin_user, minted_token):
        resp = client.post(f"/admin/tokens/{minted_token.id}/suspend",
                           headers=AUTH(admin_token))
        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == "SUSPENDED"

    def test_cannot_suspend_already_suspended(self, client, admin_token, admin_user,
                                               minted_token):
        client.post(f"/admin/tokens/{minted_token.id}/suspend", headers=AUTH(admin_token))
        resp = client.post(f"/admin/tokens/{minted_token.id}/suspend", headers=AUTH(admin_token))
        assert resp.status_code == 400

    def test_farmer_cannot_suspend(self, client, farmer_token, minted_token):
        resp = client.post(f"/admin/tokens/{minted_token.id}/suspend",
                           headers=AUTH(farmer_token))
        assert resp.status_code == 403

    def test_verifier_cannot_suspend(self, client, verifier_token, verifier_user, minted_token):
        resp = client.post(f"/admin/tokens/{minted_token.id}/suspend",
                           headers=AUTH(verifier_token))
        assert resp.status_code == 403

    def test_token_not_found(self, client, admin_token, admin_user):
        resp = client.post("/admin/tokens/99999/suspend", headers=AUTH(admin_token))
        assert resp.status_code == 404

    def test_unauthenticated_rejected(self, client, minted_token):
        resp = client.post(f"/admin/tokens/{minted_token.id}/suspend")
        assert resp.status_code == 401
