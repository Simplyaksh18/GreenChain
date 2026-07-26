"""
Phase 1 — Utility tests
Tests hash_utils and response_utils.
"""
from app.utils.hash_utils import sha256_hash
from app.utils.response_utils import success_response, error_response


class TestHashUtils:
    def test_sha256_returns_string(self):
        result = sha256_hash({"key": "value"})
        assert isinstance(result, str)

    def test_sha256_length(self):
        result = sha256_hash({"key": "value"})
        assert len(result) == 64  # SHA256 hex = 64 chars

    def test_sha256_deterministic(self):
        a = sha256_hash({"a": 1, "b": 2})
        b = sha256_hash({"b": 2, "a": 1})
        assert a == b  # sort_keys=True makes it deterministic

    def test_sha256_different_inputs(self):
        a = sha256_hash({"x": 1})
        b = sha256_hash({"x": 2})
        assert a != b

    def test_sha256_handles_nested(self):
        result = sha256_hash({"nested": {"deep": [1, 2, 3]}})
        assert len(result) == 64


class TestResponseUtils:
    def test_success_response_structure(self):
        r = success_response({"id": 1})
        assert r["success"] is True
        assert r["data"] == {"id": 1}
        assert r["message"] == "Success"

    def test_success_response_custom_message(self):
        r = success_response(None, message="Created")
        assert r["message"] == "Created"

    def test_error_response_structure(self):
        r = error_response("Something went wrong")
        assert r["success"] is False
        assert r["message"] == "Something went wrong"
        assert r["code"] is None

    def test_error_response_with_code(self):
        r = error_response("Not found", code="NOT_FOUND")
        assert r["code"] == "NOT_FOUND"
