"""
AI Helper Docstring
Purpose: JWT logic and password hashing utilizing argon2-cffi (primary) + bcrypt (legacy verify) & PyJWT.
Interactions:
- `app.config.py`: Retrieves `SECRET_KEY` and token expiration lengths.
- `app.services.auth_service.py`: Computes and verifies passwords strictly against login payloads.
"""

"""Security utilities: JWT token handling and password hashing.

All secrets are sourced from Settings — never hardcoded.

Password hashing note: new hashes are argon2id (argon2-cffi). Legacy bcrypt
hashes (produced by the previous passlib-based implementation) are still
*verified* directly via the `bcrypt` library, and callers use `needs_rehash()`
to transparently upgrade them to argon2 on the next successful login. This lets
us drop the unmaintained `passlib` dependency without invalidating any existing
password.
"""

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from argon2 import PasswordHasher
from argon2.exceptions import Argon2Error

from app.config import get_settings

# argon2id hasher with library defaults — the source of all new password hashes.
_hasher = PasswordHasher()

# bcrypt only ever consumes the first 72 bytes of a password; the previous
# passlib implementation relied on that, so we must truncate identically here or
# long passwords would (a) raise ValueError in bcrypt and (b) fail to match.
_BCRYPT_MAX_BYTES = 72

ALGORITHM = "HS256"


def hash_password(plain_password: str) -> str:
    """Hash a plaintext password using argon2id."""
    return _hasher.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against its stored hash.

    Dispatches on the hash format so both current argon2 hashes and legacy
    bcrypt hashes verify. Returns False (never raises) on any mismatch or
    malformed/unknown hash.
    """
    if hashed_password.startswith("$argon2"):
        try:
            return _hasher.verify(hashed_password, plain_password)
        except Argon2Error:
            return False

    if hashed_password.startswith("$2"):  # bcrypt: $2a$ / $2b$ / $2y$
        password_bytes = plain_password.encode("utf-8")[:_BCRYPT_MAX_BYTES]
        try:
            return bcrypt.checkpw(password_bytes, hashed_password.encode("utf-8"))
        except ValueError:
            return False

    return False


def needs_rehash(hashed_password: str) -> bool:
    """Report whether a stored hash should be re-hashed with current params.

    True for any legacy bcrypt hash (so it upgrades to argon2 on next login) and
    for argon2 hashes whose parameters have drifted from the current defaults.
    """
    if not hashed_password.startswith("$argon2"):
        return True
    return _hasher.check_needs_rehash(hashed_password)


def create_access_token(
    data: dict,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a signed JWT access token.

    Args:
        data: Claims to include in the token (must include 'sub').
        expires_delta: Custom expiry. Falls back to settings default.

    Returns:
        Encoded JWT string.
    """
    settings = get_settings()
    to_encode = data.copy()

    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    expire = datetime.now(timezone.utc) + expires_delta
    to_encode.update({"exp": expire})

    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    """Decode and validate a JWT token.

    Args:
        token: The encoded JWT string.

    Returns:
        Decoded claims dictionary.

    Raises:
        jwt.PyJWTError: If the token is invalid, expired, or tampered with.
    """
    settings = get_settings()
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
