"""
AI Helper Docstring
Purpose: JWT logic and password hashing utilizing passlib & python-jose.
Interactions:
- `app.config.py`: Retrieves `SECRET_KEY` and token expiration lengths.
- `app.services.auth_service.py`: Computes and verifies passwords strictly against login payloads.
"""

"""Security utilities: JWT token handling and password hashing.

All secrets are sourced from Settings — never hardcoded.
"""

from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import get_settings

# Bcrypt password hashing with automatic salt
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ALGORITHM = "HS256"


def hash_password(plain_password: str) -> str:
    """Hash a plaintext password using bcrypt."""
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    return pwd_context.verify(plain_password, hashed_password)


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
        JWTError: If the token is invalid, expired, or tampered with.
    """
    settings = get_settings()
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
