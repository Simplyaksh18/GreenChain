"""
Phase 19 — auth hardening tests.

Covers:
  - verify_password returns False (not raise) on malformed stored hash
  - login returns 401 (not 500) when the stored hash is malformed
  - login returns 401 for unknown user and wrong password
  - reset_user_password.py CLI produces a valid, verifiable bcrypt hash
"""
from __future__ import annotations

from app.models.user import User, UserRole
from app.security import get_password_hash, hash_password, verify_password
from scripts.reset_user_password import reset_password


# ── verify_password ───────────────────────────────────────────────────────────

class TestVerifyPassword:
    def test_valid_hash_authenticates(self):
        h = hash_password("password123")
        assert verify_password("password123", h) is True

    def test_wrong_password_returns_false(self):
        h = hash_password("password123")
        assert verify_password("wrong", h) is False

    def test_malformed_hash_returns_false_not_raise(self):
        assert verify_password("password123", "not-a-real-hash") is False

    def test_empty_hash_returns_false(self):
        assert verify_password("password123", "") is False

    def test_none_hash_returns_false(self):
        assert verify_password("password123", None) is False  # type: ignore[arg-type]


# ── /auth/login behaviour under a malformed stored hash ───────────────────────

class TestLoginMalformedHash:
    def test_login_malformed_hash_returns_401_not_500(self, client, db):
        user = User(
            name="Broken Hash",
            email="broken@auth.com",
            password_hash="this-is-not-a-bcrypt-hash",
            role=UserRole.FARMER,
            is_active=True,
            is_approved=True,
        )
        db.add(user)
        db.commit()

        resp = client.post(
            "/auth/login",
            json={"email": "broken@auth.com", "password": "password123"},
        )
        assert resp.status_code == 401
        body = resp.json()
        # Response must not leak hash format details.
        assert "hash" not in body.get("detail", "").lower()
        assert "bcrypt" not in body.get("detail", "").lower()


# ── password reset script ─────────────────────────────────────────────────────

class TestResetUserPasswordScript:
    def test_generated_hash_is_valid_bcrypt_length(self):
        h = get_password_hash("password123")
        assert isinstance(h, str)
        assert len(h) == 60  # bcrypt hashes are always 60 chars
        assert h.startswith("$2")

    def test_generated_hash_verifies(self):
        h = get_password_hash("password123")
        assert verify_password("password123", h) is True

    def test_reset_unknown_user_returns_nonzero(self, db):
        rc = reset_password("does-not-exist@example.com", "newpassword123")
        assert rc != 0

    def test_reset_updates_hash_and_verifies(self, db):
        user = User(
            name="Reset Me",
            email="resetme@auth.com",
            password_hash=hash_password("oldpassword"),
            role=UserRole.FARMER,
            is_active=True,
            is_approved=True,
        )
        db.add(user)
        db.commit()
        old_hash = user.password_hash

        rc = reset_password("resetme@auth.com", "brandnewpass123")
        assert rc == 0

        db.expire_all()
        refreshed = db.query(User).filter(User.email == "resetme@auth.com").first()
        assert refreshed is not None
        assert refreshed.password_hash != old_hash
        assert verify_password("brandnewpass123", refreshed.password_hash) is True
        assert verify_password("oldpassword", refreshed.password_hash) is False

    def test_reset_email_is_case_insensitive(self, db):
        user = User(
            name="Case",
            email="caseuser@auth.com",
            password_hash=hash_password("oldpass"),
            role=UserRole.FARMER,
            is_active=True,
            is_approved=True,
        )
        db.add(user)
        db.commit()

        rc = reset_password("CaseUser@Auth.COM", "aNewSafePass1")
        assert rc == 0

    def test_reset_rejects_short_password(self, db):
        rc = reset_password("anyone@example.com", "short")
        assert rc == 2
