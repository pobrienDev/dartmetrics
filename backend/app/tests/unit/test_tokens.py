"""Unit tests for JWT access tokens."""

import uuid
from datetime import datetime, timedelta, timezone

import jwt
import pytest

from app.common.security import (
    JWT_ALGORITHM,
    create_access_token,
    decode_access_token,
)
from app.config import get_settings


def test_token_round_trip_returns_user_id():
    user_id = uuid.uuid4()
    token = create_access_token(user_id)
    assert decode_access_token(token) == user_id


def test_expired_token_is_rejected():
    now = datetime.now(timezone.utc)
    expired = jwt.encode(
        {"sub": str(uuid.uuid4()), "iat": now - timedelta(hours=2), "exp": now - timedelta(hours=1)},
        get_settings().secret_key,
        algorithm=JWT_ALGORITHM,
    )
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_access_token(expired)


def test_token_signed_with_wrong_key_is_rejected():
    forged = jwt.encode(
        {"sub": str(uuid.uuid4()), "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
        "attacker-key-padded-to-a-realistic-32-byte-length",
        algorithm=JWT_ALGORITHM,
    )
    with pytest.raises(jwt.InvalidSignatureError):
        decode_access_token(forged)


def test_tampered_token_is_rejected():
    token = create_access_token(uuid.uuid4())
    header, payload, signature = token.split(".")
    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token(f"{header}.{payload}x.{signature}")
