"""
AI Helper Docstring
Purpose: Pytests proving that JWT decodification strings explicitly match payloads correctly and expire exactly when required.
Interactions:
- Verifies functionality strictly on `app.security.py`.
"""

"""Tests for app.security module — JWT and password hashing."""

import time
from datetime import timedelta

import pytest
from jose import JWTError

from app.security import (
    create_access_token,
    decode_token,
    hash_password,
    verify_password,
)


class TestPasswordHashing:
    """Tests for bcrypt password hashing."""

    def test_hash_password_returns_bcrypt_hash(self):
        hashed = hash_password("mypassword")
        assert hashed.startswith("$2b$")
        assert hashed != "mypassword"

    def test_verify_correct_password(self):
        hashed = hash_password("mypassword")
        assert verify_password("mypassword", hashed) is True

    def test_verify_wrong_password(self):
        hashed = hash_password("mypassword")
        assert verify_password("wrongpassword", hashed) is False

    def test_different_hashes_for_same_password(self):
        """Bcrypt uses random salts, so same password produces different hashes."""
        h1 = hash_password("mypassword")
        h2 = hash_password("mypassword")
        assert h1 != h2
        # Both should still verify
        assert verify_password("mypassword", h1)
        assert verify_password("mypassword", h2)


class TestJWT:
    """Tests for JWT token creation and decoding."""

    def test_create_access_token_contains_claims(self):
        token = create_access_token(data={"sub": "user-123", "role": "admin"})
        payload = decode_token(token)
        assert payload["sub"] == "user-123"
        assert payload["role"] == "admin"
        assert "exp" in payload

    def test_decode_valid_token(self):
        token = create_access_token(data={"sub": "user-456"})
        payload = decode_token(token)
        assert payload["sub"] == "user-456"

    def test_decode_expired_token_raises(self):
        token = create_access_token(
            data={"sub": "user-789"},
            expires_delta=timedelta(seconds=-1),  # Already expired
        )
        with pytest.raises(JWTError):
            decode_token(token)

    def test_decode_invalid_token_raises(self):
        with pytest.raises(JWTError):
            decode_token("not.a.valid.token")

    def test_decode_tampered_token_raises(self):
        token = create_access_token(data={"sub": "user-123"})
        # Tamper with the token
        tampered = token[:-5] + "XXXXX"
        with pytest.raises(JWTError):
            decode_token(tampered)

    def test_custom_expiry(self):
        token = create_access_token(
            data={"sub": "user-123"},
            expires_delta=timedelta(hours=2),
        )
        payload = decode_token(token)
        # Should expire roughly 2 hours from now
        assert payload["exp"] > time.time()
        assert payload["exp"] < time.time() + 7201
