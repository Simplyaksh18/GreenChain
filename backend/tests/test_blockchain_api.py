"""
Phase 5 — Blockchain API tests.
Covers: POST /blockchain/anchor-report/{report_id}
        GET  /blockchain/report/{report_id}
"""
import re
import pytest

AUTH = lambda t: {"Authorization": f"Bearer {t}"}
TX_PATTERN = re.compile(r"^0x[0-9a-f]{64}$")


class TestAnchorReport:
    def test_admin_can_anchor_verified_report(self, client, admin_token, admin_user,
                                               verified_report):
        resp = client.post(f"/blockchain/anchor-report/{verified_report.id}",
                           headers=AUTH(admin_token))
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["carbon_report_id"] == verified_report.id
        assert data["action_type"] == "REPORT_HASH"
        assert TX_PATTERN.match(data["tx_hash"])
        assert data["blockchain_network"] == "MOCK_POLYGON_AMOY"
        assert data["contract_address"] == "0xMockGreenChainContract000000000000000000"

    def test_anchor_idempotent_returns_same_tx(self, client, admin_token, admin_user,
                                                verified_report):
        r1 = client.post(f"/blockchain/anchor-report/{verified_report.id}",
                         headers=AUTH(admin_token))
        r2 = client.post(f"/blockchain/anchor-report/{verified_report.id}",
                         headers=AUTH(admin_token))
        assert r1.status_code == 201
        assert r2.status_code == 201
        assert r1.json()["tx_hash"] == r2.json()["tx_hash"]

    def test_farmer_cannot_anchor(self, client, farmer_token, verified_report):
        resp = client.post(f"/blockchain/anchor-report/{verified_report.id}",
                           headers=AUTH(farmer_token))
        assert resp.status_code == 403

    def test_verifier_cannot_anchor(self, client, verifier_token, verifier_user,
                                     verified_report):
        resp = client.post(f"/blockchain/anchor-report/{verified_report.id}",
                           headers=AUTH(verifier_token))
        assert resp.status_code == 403

    def test_fpo_cannot_anchor(self, client, fpo_token, fpo_profile, verified_report):
        resp = client.post(f"/blockchain/anchor-report/{verified_report.id}",
                           headers=AUTH(fpo_token))
        assert resp.status_code == 403

    def test_unverified_report_cannot_anchor(self, client, admin_token, admin_user,
                                              carbon_report_draft):
        resp = client.post(f"/blockchain/anchor-report/{carbon_report_draft.id}",
                           headers=AUTH(admin_token))
        assert resp.status_code == 400

    def test_submitted_report_cannot_anchor(self, client, admin_token, admin_user,
                                             carbon_report_submitted):
        resp = client.post(f"/blockchain/anchor-report/{carbon_report_submitted.id}",
                           headers=AUTH(admin_token))
        assert resp.status_code == 400

    def test_report_not_found(self, client, admin_token, admin_user):
        resp = client.post("/blockchain/anchor-report/99999", headers=AUTH(admin_token))
        assert resp.status_code == 404

    def test_unauthenticated_rejected(self, client, verified_report):
        resp = client.post(f"/blockchain/anchor-report/{verified_report.id}")
        assert resp.status_code == 401


class TestGetReportTransactions:
    def test_farmer_gets_own_report_transactions(self, client, farmer_token, admin_token,
                                                  admin_user, verified_report):
        client.post(f"/blockchain/anchor-report/{verified_report.id}",
                    headers=AUTH(admin_token))
        resp = client.get(f"/blockchain/report/{verified_report.id}",
                          headers=AUTH(farmer_token))
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        assert data[0]["carbon_report_id"] == verified_report.id

    def test_verifier_can_get_transactions(self, client, verifier_token, verifier_user,
                                            admin_token, admin_user, verified_report):
        client.post(f"/blockchain/anchor-report/{verified_report.id}",
                    headers=AUTH(admin_token))
        resp = client.get(f"/blockchain/report/{verified_report.id}",
                          headers=AUTH(verifier_token))
        assert resp.status_code == 200

    def test_admin_can_get_transactions(self, client, admin_token, admin_user, verified_report):
        client.post(f"/blockchain/anchor-report/{verified_report.id}",
                    headers=AUTH(admin_token))
        resp = client.get(f"/blockchain/report/{verified_report.id}",
                          headers=AUTH(admin_token))
        assert resp.status_code == 200

    def test_farmer2_cannot_get_other_farm_transactions(self, client, farmer2_token,
                                                          admin_token, admin_user,
                                                          verified_report):
        client.post(f"/blockchain/anchor-report/{verified_report.id}",
                    headers=AUTH(admin_token))
        resp = client.get(f"/blockchain/report/{verified_report.id}",
                          headers=AUTH(farmer2_token))
        assert resp.status_code == 403

    def test_empty_list_when_no_transactions(self, client, farmer_token, verified_report):
        resp = client.get(f"/blockchain/report/{verified_report.id}",
                          headers=AUTH(farmer_token))
        assert resp.status_code == 200
        assert resp.json() == []

    def test_report_not_found(self, client, farmer_token):
        resp = client.get("/blockchain/report/99999", headers=AUTH(farmer_token))
        assert resp.status_code == 404

    def test_unauthenticated_rejected(self, client, verified_report):
        resp = client.get(f"/blockchain/report/{verified_report.id}")
        assert resp.status_code == 401
