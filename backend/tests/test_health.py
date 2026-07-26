"""
Phase 19 — public health endpoint tests.
"""


class TestHealthEndpoint:
    def test_health_returns_200(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_health_payload_shape(self, client):
        resp = client.get("/health")
        body = resp.json()
        assert body["status"] == "ok"
        assert body["db"] in ("ok", "unavailable")
        assert "environment" in body

    def test_health_does_not_leak_secrets(self, client):
        resp = client.get("/health")
        body_text = resp.text.lower()
        for banned in (
            "postgres",
            "postgresql",
            "password",
            "secret",
            "private_key",
            "razorpay_key",
            "web3_",
            "database_url",
        ):
            assert banned not in body_text, f"health response leaked {banned!r}"

    def test_health_requires_no_auth(self, client):
        # Public endpoint — no Authorization header.
        resp = client.get("/health")
        assert resp.status_code == 200
