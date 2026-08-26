"""Password hashing (dev plan section 12).

Argon2id via pwdlib — never hand-rolled hashing. The returned hash
string embeds the algorithm, parameters, and a random salt, so
verify_password needs no extra inputs and parameter upgrades can be
detected later via pwdlib's rehash support.
"""

import uuid
from datetime import datetime, timedelta, timezone

import jwt
from pwdlib import PasswordHash

from app.config import get_settings

_hasher = PasswordHash.recommended()

JWT_ALGORITHM = "HS256"


def hash_password(plain_password: str) -> str:
    return _hasher.hash(plain_password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    return _hasher.verify(plain_password, password_hash)


def create_access_token(user_id: uuid.UUID) -> str:
    """Signed JWT identifying a user, valid for the configured lifetime."""
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> uuid.UUID:
    """Return the user id from a valid token.

    Raises jwt.InvalidTokenError (or a subclass such as
    ExpiredSignatureError) for anything expired, tampered, or malformed.
    """
    payload = jwt.decode(
        token, get_settings().secret_key, algorithms=[JWT_ALGORITHM]
    )
    return uuid.UUID(payload["sub"])
