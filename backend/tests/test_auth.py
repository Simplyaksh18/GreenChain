"""
Phase 1 — Auth endpoint tests
Covers: POST /auth/register, POST /auth/login, GET /auth/me
"""
import pytest
from app.models.user import UserRole


# ---------------------------------------------------------------------------
# POST /auth/register
# ---------------------------------------------------------------------------
class TestRegister:
    def test_register_farmer_success(self, client):
        resp = client.post("/auth/register", json={
            "name": "New Farmer",
            "email": "newfarmer@auth.com",
            "password": "password123",
            "role": "FARMER",
        })
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["email"] == "newfarmer@auth.com"
        assert data["role"] == "FARMER"
        assert data["is_active"] is True
        # Farmers are auto-approved
        assert data["is_approved"] is True
        assert "password_hash" not in data
        assert "password" not in data

    def test_register_fpo_not_auto_approved(self, client):
        resp = client.post("/auth/register", json={
            "name": "New FPO",
            "email": "newfpo@auth.com",
            "password": "password123",
            "role": "FPO",
        })
        assert resp.status_code == 201, resp.text
        assert resp.json()["is_approved"] is False

    def test_register_verifier_not_auto_approved(self, client):
        resp = client.post("/auth/register", json={
            "name": "New Verifier",
            "email": "newverifier@auth.com",
            "password": "password123",
            "role": "VERIFIER",
        })
        assert resp.status_code == 201
        assert resp.json()["is_approved"] is False

    def test_register_admin_not_auto_approved(self, client):
        resp = client.post("/auth/register", json={
            "name": "New Admin",
            "email": "newadmin@auth.com",
            "password": "password123",
            "role": "ADMIN",
        })
        assert resp.status_code == 201
        assert resp.json()["is_approved"] is False

    def test_register_duplicate_email(self, client):
        payload = {
            "name": "Dup User",
            "email": "dup@auth.com",
            "password": "password123",
            "role": "FARMER",
        }
        client.post("/auth/register", json=payload)
        resp = client.post("/auth/register", json=payload)
        assert resp.status_code == 400
        assert "already registered" in resp.json()["detail"].lower()

    def test_register_invalid_email(self, client):
        resp = client.post("/auth/register", json={
            "name": "Bad Email",
            "email": "not-an-email",
            "password": "password123",
            "role": "FARMER",
        })
        assert resp.status_code == 422

    def test_register_short_password(self, client):
        resp = client.post("/auth/register", json={
            "name": "Short Pass",
            "email": "short@auth.com",
            "password": "abc",
            "role": "FARMER",
        })
        assert resp.status_code == 422

    def test_register_invalid_role(self, client):
        resp = client.post("/auth/register", json={
            "name": "Bad Role",
            "email": "badrole@auth.com",
            "password": "password123",
            "role": "SUPERUSER",
        })
        assert resp.status_code == 422

    def test_register_missing_fields(self, client):
        resp = client.post("/auth/register", json={"name": "Missing"})
        assert resp.status_code == 422

    def test_register_response_has_id_and_created_at(self, client):
        resp = client.post("/auth/register", json={
            "name": "Complete",
            "email": "complete@auth.com",
            "password": "password123",
            "role": "FARMER",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert "id" in data
        assert "created_at" in data


# ---------------------------------------------------------------------------
# POST /auth/login
# ---------------------------------------------------------------------------
class TestLogin:
    def test_login_success(self, client, farmer_user):
        resp = client.post("/auth/login", json={
            "email": "farmer@test.com",
            "password": "password123",
        })
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_login_wrong_password(self, client, farmer_user):
        resp = client.post("/auth/login", json={
            "email": "farmer@test.com",
            "password": "wrongpassword",
        })
        assert resp.status_code == 401

    def test_login_unknown_email(self, client):
        resp = client.post("/auth/login", json={
            "email": "nobody@test.com",
            "password": "password123",
        })
        assert resp.status_code == 401

    def test_login_inactive_user(self, client, inactive_user):
        resp = client.post("/auth/login", json={
            "email": "inactive@test.com",
            "password": "password123",
        })
        assert resp.status_code == 403

    def test_login_invalid_email_format(self, client):
        resp = client.post("/auth/login", json={
            "email": "not-an-email",
            "password": "password123",
        })
        assert resp.status_code == 422

    def test_login_all_roles(self, client, farmer_user, fpo_user, verifier_user, admin_user):
        for email in ["farmer@test.com", "fpo@test.com", "verifier@test.com", "admin@test.com"]:
            resp = client.post("/auth/login", json={"email": email, "password": "password123"})
            assert resp.status_code == 200, f"Login failed for {email}"


# ---------------------------------------------------------------------------
# GET /auth/me
# ---------------------------------------------------------------------------
class TestGetMe:
    def test_get_me_farmer(self, client, farmer_user, farmer_token):
        resp = client.get("/auth/me", headers={"Authorization": f"Bearer {farmer_token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "farmer@test.com"
        assert data["role"] == "FARMER"

    def test_get_me_fpo(self, client, fpo_user, fpo_token):
        resp = client.get("/auth/me", headers={"Authorization": f"Bearer {fpo_token}"})
        assert resp.status_code == 200
        assert resp.json()["role"] == "FPO"

    def test_get_me_verifier(self, client, verifier_user, verifier_token):
        resp = client.get("/auth/me", headers={"Authorization": f"Bearer {verifier_token}"})
        assert resp.status_code == 200
        assert resp.json()["role"] == "VERIFIER"

    def test_get_me_admin(self, client, admin_user, admin_token):
        resp = client.get("/auth/me", headers={"Authorization": f"Bearer {admin_token}"})
        assert resp.status_code == 200
        assert resp.json()["role"] == "ADMIN"

    def test_get_me_no_token(self, client):
        resp = client.get("/auth/me")
        assert resp.status_code == 401

    def test_get_me_invalid_token(self, client):
        resp = client.get("/auth/me", headers={"Authorization": "Bearer invalidtoken123"})
        assert resp.status_code == 401

    def test_get_me_malformed_header(self, client):
        resp = client.get("/auth/me", headers={"Authorization": "notbearer token"})
        assert resp.status_code == 401

    def test_get_me_no_sensitive_data(self, client, farmer_user, farmer_token):
        resp = client.get("/auth/me", headers={"Authorization": f"Bearer {farmer_token}"})
        data = resp.json()
        assert "password_hash" not in data
        assert "password" not in data


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
class TestHealthCheck:
    def test_root(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["service"] == "GreenChain API"
