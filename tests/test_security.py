"""
AI Helper Docstring
Purpose: Pytests proving that JWT decodification strings explicitly match payloads correctly and expire exactly when required.
Interactions:
- Verifies functionality strictly on `app.security.py`.
"""

"""Tests for app.security module — JWT and password hashing."""

import time
from datetime import timedelta

import bcrypt
import jwt
import pytest

from app.security import (
    create_access_token,
    decode_token,
    hash_password,
    needs_rehash,
    verify_password,
)


def _legacy_bcrypt_hash(password: str) -> str:
    """Produce a bcrypt hash the way the old passlib implementation would have,
    for exercising the legacy-verify / rehash migration path."""
    truncated = password.encode("utf-8")[:72]
    return bcrypt.hashpw(truncated, bcrypt.gensalt()).decode("utf-8")


class TestPasswordHashing:
    """Tests for argon2 password hashing."""

    def test_hash_password_returns_argon2_hash(self):
        hashed = hash_password("mypassword")
        assert hashed.startswith("$argon2")
        assert hashed != "mypassword"

    def test_verify_correct_password(self):
        hashed = hash_password("mypassword")
        assert verify_password("mypassword", hashed) is True

    def test_verify_wrong_password(self):
        hashed = hash_password("mypassword")
        assert verify_password("wrongpassword", hashed) is False

    def test_different_hashes_for_same_password(self):
        """Argon2 uses random salts, so same password produces different hashes."""
        h1 = hash_password("mypassword")
        h2 = hash_password("mypassword")
        assert h1 != h2
        # Both should still verify
        assert verify_password("mypassword", h1)
        assert verify_password("mypassword", h2)

    def test_verify_unknown_hash_format_returns_false(self):
        assert verify_password("mypassword", "not-a-real-hash") is False


class TestLegacyBcryptMigration:
    """The migration path: existing bcrypt hashes must keep working and upgrade."""

    def test_legacy_bcrypt_hash_still_verifies(self):
        hashed = _legacy_bcrypt_hash("mypassword")
        assert hashed.startswith("$2")
        assert verify_password("mypassword", hashed) is True
        assert verify_password("wrongpassword", hashed) is False

    def test_needs_rehash_true_for_bcrypt_false_for_argon2(self):
        assert needs_rehash(_legacy_bcrypt_hash("mypassword")) is True
        assert needs_rehash(hash_password("mypassword")) is False

    def test_long_password_verifies_against_legacy_bcrypt(self):
        """Passwords >72 bytes must verify without raising (bcrypt truncation)."""
        long_password = "a" * 100
        hashed = _legacy_bcrypt_hash(long_password)
        assert verify_password(long_password, hashed) is True


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
        with pytest.raises(jwt.PyJWTError):
            decode_token(token)

    def test_decode_invalid_token_raises(self):
        with pytest.raises(jwt.PyJWTError):
            decode_token("not.a.valid.token")

    def test_decode_tampered_token_raises(self):
        token = create_access_token(data={"sub": "user-123"})
        # Tamper with the token
        tampered = token[:-5] + "XXXXX"
        with pytest.raises(jwt.PyJWTError):
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
