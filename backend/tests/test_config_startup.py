"""
Focused tests for SECRET_KEY + CORS_ORIGINS startup validation (Task 2).

These tests never touch the real running app instance's CORS middleware —
they construct fresh Settings objects and call validate_startup_config() /
get_cors_origins() directly. That keeps the tests deterministic and
independent of the module-level `settings` singleton loaded by conftest.
"""
from __future__ import annotations

import pytest

from app.config import (
    ConfigurationError,
    Settings,
    get_cors_origins,
    is_devlike,
    is_prodlike,
    validate_startup_config,
)


def _mk(
    *,
    app_env: str,
    secret_key: str = "",
    cors_origins: str = "",
) -> Settings:
    """Build a minimal Settings object with only the fields under test."""
    return Settings(
        APP_ENV=app_env,
        SECRET_KEY=secret_key,
        CORS_ORIGINS=cors_origins,
    )


# ── environment classification ───────────────────────────────────────────────

class TestEnvClassification:
    @pytest.mark.parametrize("env", ["development", "dev", "test", "testing", "", "DEV", " Dev "])
    def test_devlike(self, env):
        assert is_devlike(env)
        assert not is_prodlike(env)

    @pytest.mark.parametrize("env", ["staging", "production", "prod", "PROD", " staging "])
    def test_prodlike(self, env):
        assert is_prodlike(env)
        assert not is_devlike(env)


# ── SECRET_KEY validation ────────────────────────────────────────────────────

class TestSecretKeyValidation:
    def test_development_missing_secret_gets_dev_fallback(self):
        s = _mk(app_env="development", secret_key="")
        validate_startup_config(s)
        # Fallback applied — not the known-unsafe production default.
        assert s.SECRET_KEY.startswith("dev-only-unsafe-fallback")
        assert "supersecretkey-change-in-production" != s.SECRET_KEY

    def test_test_env_uses_supplied_secret(self):
        s = _mk(app_env="test", secret_key="deterministic-test-key-32-chars-min")
        validate_startup_config(s)
        assert s.SECRET_KEY == "deterministic-test-key-32-chars-min"

    def test_staging_missing_secret_raises(self):
        s = _mk(app_env="staging", secret_key="")
        with pytest.raises(ConfigurationError) as exc:
            validate_startup_config(s)
        assert "SECRET_KEY" in str(exc.value)

    def test_production_missing_secret_raises(self):
        s = _mk(app_env="production", secret_key="")
        with pytest.raises(ConfigurationError):
            validate_startup_config(s)

    def test_staging_rejects_known_default(self):
        s = _mk(
            app_env="staging",
            secret_key="supersecretkey-change-in-production",
            cors_origins="https://a.example",
        )
        with pytest.raises(ConfigurationError) as exc:
            validate_startup_config(s)
        assert "default" in str(exc.value).lower() or "unsafe" in str(exc.value).lower()

    def test_production_rejects_too_short(self):
        s = _mk(
            app_env="production",
            secret_key="short-key",
            cors_origins="https://a.example",
        )
        with pytest.raises(ConfigurationError) as exc:
            validate_startup_config(s)
        assert "32" in str(exc.value) or "short" in str(exc.value).lower()

    def test_production_rejects_whitespace_only(self):
        s = _mk(
            app_env="production",
            secret_key="                                    ",
            cors_origins="https://a.example",
        )
        with pytest.raises(ConfigurationError):
            validate_startup_config(s)

    def test_staging_accepts_valid_secret(self):
        s = _mk(
            app_env="staging",
            secret_key="a" * 64,
            cors_origins="https://admin.greenchain.example",
        )
        # Should not raise.
        validate_startup_config(s)

    def test_error_message_does_not_leak_secret(self):
        secret = "supersecretkey-change-in-production"
        s = _mk(app_env="production", secret_key=secret, cors_origins="https://x")
        with pytest.raises(ConfigurationError) as exc:
            validate_startup_config(s)
        assert secret not in str(exc.value)


# ── JWT still works with a valid configured key ──────────────────────────────

class TestJwtStillWorks:
    def test_jwt_encode_decode_roundtrip(self):
        from jose import jwt
        s = _mk(
            app_env="staging",
            secret_key="k" * 64,
            cors_origins="https://ok.example",
        )
        validate_startup_config(s)
        token = jwt.encode({"sub": "1"}, s.SECRET_KEY, algorithm=s.ALGORITHM)
        decoded = jwt.decode(token, s.SECRET_KEY, algorithms=[s.ALGORITHM])
        assert decoded["sub"] == "1"


# ── CORS parsing ─────────────────────────────────────────────────────────────

class TestCorsParsing:
    def test_comma_separated_parses(self):
        s = _mk(app_env="staging", cors_origins="https://a.example,https://b.example")
        assert get_cors_origins(s) == ["https://a.example", "https://b.example"]

    def test_whitespace_trimmed(self):
        s = _mk(app_env="staging", cors_origins="  https://a.example ,  https://b.example  ")
        assert get_cors_origins(s) == ["https://a.example", "https://b.example"]

    def test_empty_entries_ignored(self):
        s = _mk(app_env="staging", cors_origins="https://a.example, ,,https://b.example,")
        assert get_cors_origins(s) == ["https://a.example", "https://b.example"]

    def test_duplicates_removed(self):
        s = _mk(app_env="staging", cors_origins="https://a.example,https://a.example,https://b.example")
        assert get_cors_origins(s) == ["https://a.example", "https://b.example"]

    def test_dev_empty_defaults_to_wildcard(self):
        s = _mk(app_env="development", cors_origins="")
        assert get_cors_origins(s) == ["*"]

    def test_prod_empty_returns_empty_list(self):
        s = _mk(app_env="production", cors_origins="")
        assert get_cors_origins(s) == []

    def test_staging_missing_cors_raises(self):
        s = _mk(app_env="staging", secret_key="k" * 64, cors_origins="")
        with pytest.raises(ConfigurationError) as exc:
            validate_startup_config(s)
        assert "CORS_ORIGINS" in str(exc.value)

    def test_production_wildcard_rejected(self):
        s = _mk(app_env="production", secret_key="k" * 64, cors_origins="*")
        with pytest.raises(ConfigurationError) as exc:
            validate_startup_config(s)
        assert "*" in str(exc.value) or "wildcard" in str(exc.value).lower()

    def test_production_valid_list_accepted(self):
        s = _mk(
            app_env="production",
            secret_key="k" * 64,
            cors_origins="https://one.example, https://two.example",
        )
        validate_startup_config(s)  # no raise
        assert get_cors_origins(s) == ["https://one.example", "https://two.example"]


# ── App-level CORS middleware still lets requests through ────────────────────

class TestApiCorsBehaviour:
    def test_health_endpoint_still_responds(self, client):
        # Sanity: the middleware wiring didn't break basic requests.
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_preflight_from_allowed_origin(self, client):
        # In the test env APP_ENV defaults to "development" via .env.test,
        # so get_cors_origins() returns ["*"] and preflight succeeds.
        resp = client.options(
            "/auth/login",
            headers={
                "Origin": "http://localhost:8081",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )
        # 200 (allowed) or 204 depending on Starlette version; either is fine.
        assert resp.status_code in (200, 204)

    def test_health_response_does_not_leak_secret(self, client):
        # Belt-and-braces: /health must never surface SECRET_KEY.
        resp = client.get("/health")
        body = resp.text
        assert "SECRET_KEY" not in body
        assert "supersecretkey" not in body.lower()
