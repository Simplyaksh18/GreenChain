"""
Phase 5 — Admin token summary API tests.
Covers: GET /admin/token-summary
"""
import pytest

AUTH = lambda t: {"Authorization": f"Bearer {t}"}


class TestTokenSummary:
    def test_admin_gets_summary(self, client, admin_token, admin_user):
        resp = client.get("/admin/token-summary", headers=AUTH(admin_token))
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "total_tokens" in data
        assert "total_minted_credits" in data
        assert "active_tokens" in data
        assert "retired_tokens" in data
        assert "suspended_tokens" in data
        assert "zero_credit_certificates" in data

    def test_empty_summary_when_no_tokens(self, client, admin_token, admin_user):
        resp = client.get("/admin/token-summary", headers=AUTH(admin_token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_tokens"] == 0
        assert data["total_minted_credits"] == 0
        assert data["active_tokens"] == 0
        assert data["retired_tokens"] == 0
        assert data["suspended_tokens"] == 0
        assert data["zero_credit_certificates"] == 0

    def test_total_tokens_counts_all(self, client, admin_token, admin_user,
                                      verified_report, minted_token):
        resp = client.get("/admin/token-summary", headers=AUTH(admin_token))
        data = resp.json()
        assert data["total_tokens"] == 1
        assert data["active_tokens"] == 1

    def test_total_minted_credits_summed(self, client, admin_token, admin_user,
                                          verified_report, minted_token):
        resp = client.get("/admin/token-summary", headers=AUTH(admin_token))
        data = resp.json()
        assert data["total_minted_credits"] == minted_token.credit_amount

    def test_retired_count(self, client, admin_token, admin_user, minted_token):
        client.post(f"/admin/tokens/{minted_token.id}/retire", headers=AUTH(admin_token))
        resp = client.get("/admin/token-summary", headers=AUTH(admin_token))
        data = resp.json()
        assert data["retired_tokens"] == 1
        assert data["active_tokens"] == 0

    def test_suspended_count(self, client, admin_token, admin_user, minted_token):
        client.post(f"/admin/tokens/{minted_token.id}/suspend", headers=AUTH(admin_token))
        resp = client.get("/admin/token-summary", headers=AUTH(admin_token))
        data = resp.json()
        assert data["suspended_tokens"] == 1
        assert data["active_tokens"] == 0

    def test_zero_credit_certificate_counted(self, client, admin_token, admin_user,
                                              zero_credit_verified_report):
        client.post(f"/admin/tokens/mint/{zero_credit_verified_report.id}",
                    headers=AUTH(admin_token))
        resp = client.get("/admin/token-summary", headers=AUTH(admin_token))
        data = resp.json()
        assert data["zero_credit_certificates"] == 1
        assert data["total_minted_credits"] == 0

    def test_farmer_cannot_access_summary(self, client, farmer_token):
        resp = client.get("/admin/token-summary", headers=AUTH(farmer_token))
        assert resp.status_code == 403

    def test_verifier_cannot_access_summary(self, client, verifier_token, verifier_user):
        resp = client.get("/admin/token-summary", headers=AUTH(verifier_token))
        assert resp.status_code == 403

    def test_unauthenticated_rejected(self, client):
        resp = client.get("/admin/token-summary")
        assert resp.status_code == 401
