"""
Phase 1 — Security unit tests
Tests JWT creation/decoding and password hashing.
"""
import time
from datetime import timedelta
from app.security import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
)


class TestPasswordHashing:
    def test_hash_is_not_plain(self):
        h = hash_password("hello")
        assert h != "hello"

    def test_verify_correct(self):
        h = hash_password("correct")
        assert verify_password("correct", h) is True

    def test_verify_wrong(self):
        h = hash_password("correct")
        assert verify_password("wrong", h) is False

    def test_two_hashes_of_same_password_differ(self):
        h1 = hash_password("same")
        h2 = hash_password("same")
        assert h1 != h2  # bcrypt salt is random


class TestJWT:
    def test_create_and_decode(self):
        token = create_access_token({"sub": "42", "role": "FARMER"})
        payload = decode_access_token(token)
        assert payload is not None
        assert payload["sub"] == "42"
        assert payload["role"] == "FARMER"

    def test_invalid_token_returns_none(self):
        assert decode_access_token("not.a.token") is None

    def test_expired_token_returns_none(self):
        token = create_access_token({"sub": "1"}, expires_delta=timedelta(seconds=-1))
        assert decode_access_token(token) is None

    def test_token_has_exp_claim(self):
        token = create_access_token({"sub": "1"})
        payload = decode_access_token(token)
        assert "exp" in payload
