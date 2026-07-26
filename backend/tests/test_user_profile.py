"""
Phase 8 — User profile endpoint tests.

Tests GET /users/me and PATCH /users/me.
"""
import pytest


class TestGetMyProfile:
    def test_farmer_gets_own_profile(self, client, farmer_token, farmer_user):
        resp = client.get(
            "/users/me",
            headers={"Authorization": f"Bearer {farmer_token}"},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["id"] == farmer_user.id
        assert data["email"] == farmer_user.email
        assert data["name"] == farmer_user.name
        assert data["role"] == "FARMER"
        assert data["is_active"] is True
        assert data["is_approved"] is True

    def test_profile_includes_wallet_address_field(self, client, farmer_token):
        resp = client.get(
            "/users/me",
            headers={"Authorization": f"Bearer {farmer_token}"},
        )
        data = resp.json()
        assert "wallet_address" in data
        # Default is None
        assert data["wallet_address"] is None

    def test_profile_includes_created_at(self, client, farmer_token):
        resp = client.get(
            "/users/me",
            headers={"Authorization": f"Bearer {farmer_token}"},
        )
        assert "created_at" in resp.json()

    def test_admin_gets_own_profile(self, client, admin_token, admin_user):
        resp = client.get(
            "/users/me",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["role"] == "ADMIN"

    def test_verifier_gets_own_profile(self, client, verifier_token):
        resp = client.get(
            "/users/me",
            headers={"Authorization": f"Bearer {verifier_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["role"] == "VERIFIER"

    def test_fpo_gets_own_profile(self, client, fpo_token):
        resp = client.get(
            "/users/me",
            headers={"Authorization": f"Bearer {fpo_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["role"] == "FPO"

    def test_unauthenticated_returns_401(self, client):
        resp = client.get("/users/me")
        assert resp.status_code == 401


class TestUpdateMyProfile:
    def test_update_name(self, client, farmer_token):
        resp = client.patch(
            "/users/me",
            json={"name": "Updated Farmer Name"},
            headers={"Authorization": f"Bearer {farmer_token}"},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["name"] == "Updated Farmer Name"

    def test_update_wallet_address_valid(self, client, farmer_token):
        valid_wallet = "0x" + "a" * 40
        resp = client.patch(
            "/users/me",
            json={"wallet_address": valid_wallet},
            headers={"Authorization": f"Bearer {farmer_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["wallet_address"] == valid_wallet

    def test_update_both_name_and_wallet(self, client, admin_token):
        wallet = "0x" + "b" * 40
        resp = client.patch(
            "/users/me",
            json={"name": "Admin Updated", "wallet_address": wallet},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Admin Updated"
        assert data["wallet_address"] == wallet

    def test_clear_wallet_address_with_null(self, client, farmer_token):
        # First set a wallet
        wallet = "0x" + "c" * 40
        client.patch(
            "/users/me",
            json={"wallet_address": wallet},
            headers={"Authorization": f"Bearer {farmer_token}"},
        )
        # Then clear it
        resp = client.patch(
            "/users/me",
            json={"wallet_address": None},
            headers={"Authorization": f"Bearer {farmer_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["wallet_address"] is None

    def test_empty_payload_is_noop(self, client, farmer_token, farmer_user):
        resp = client.patch(
            "/users/me",
            json={},
            headers={"Authorization": f"Bearer {farmer_token}"},
        )
        assert resp.status_code == 200
        # Name should be unchanged
        assert resp.json()["name"] == farmer_user.name

    def test_unauthenticated_returns_401(self, client):
        resp = client.patch("/users/me", json={"name": "Hacker"})
        assert resp.status_code == 401

    def test_update_persists_on_subsequent_get(self, client, fpo_token):
        wallet = "0x" + "d" * 40
        client.patch(
            "/users/me",
            json={"name": "New FPO Name", "wallet_address": wallet},
            headers={"Authorization": f"Bearer {fpo_token}"},
        )
        resp = client.get(
            "/users/me",
            headers={"Authorization": f"Bearer {fpo_token}"},
        )
        data = resp.json()
        assert data["name"] == "New FPO Name"
        assert data["wallet_address"] == wallet


class TestWalletValidation:
    def test_invalid_wallet_not_hex(self, client, farmer_token):
        resp = client.patch(
            "/users/me",
            json={"wallet_address": "0xGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGG"},
            headers={"Authorization": f"Bearer {farmer_token}"},
        )
        assert resp.status_code == 422

    def test_invalid_wallet_too_short(self, client, farmer_token):
        resp = client.patch(
            "/users/me",
            json={"wallet_address": "0xabc"},
            headers={"Authorization": f"Bearer {farmer_token}"},
        )
        assert resp.status_code == 422

    def test_invalid_wallet_no_0x_prefix(self, client, farmer_token):
        resp = client.patch(
            "/users/me",
            json={"wallet_address": "a" * 42},
            headers={"Authorization": f"Bearer {farmer_token}"},
        )
        assert resp.status_code == 422

    def test_invalid_wallet_too_long(self, client, farmer_token):
        resp = client.patch(
            "/users/me",
            json={"wallet_address": "0x" + "a" * 41},
            headers={"Authorization": f"Bearer {farmer_token}"},
        )
        assert resp.status_code == 422

    def test_valid_wallet_mixed_case(self, client, farmer_token):
        wallet = "0xAbCdEf0123456789AbCdEf0123456789AbCdEf01"
        resp = client.patch(
            "/users/me",
            json={"wallet_address": wallet},
            headers={"Authorization": f"Bearer {farmer_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["wallet_address"] == wallet

    def test_empty_string_wallet_clears_value(self, client, farmer_token):
        resp = client.patch(
            "/users/me",
            json={"wallet_address": ""},
            headers={"Authorization": f"Bearer {farmer_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["wallet_address"] is None

    def test_empty_name_rejected(self, client, farmer_token):
        resp = client.patch(
            "/users/me",
            json={"name": ""},
            headers={"Authorization": f"Bearer {farmer_token}"},
        )
        assert resp.status_code == 422

    def test_blank_name_rejected(self, client, farmer_token):
        resp = client.patch(
            "/users/me",
            json={"name": "   "},
            headers={"Authorization": f"Bearer {farmer_token}"},
        )
        assert resp.status_code == 422

    def test_name_trimmed_on_update(self, client, farmer_token):
        resp = client.patch(
            "/users/me",
            json={"name": "  Padded Name  "},
            headers={"Authorization": f"Bearer {farmer_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Padded Name"
