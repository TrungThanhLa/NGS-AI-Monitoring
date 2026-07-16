from datetime import datetime, timedelta, timezone

import jwt
import pytest

from backend.auth.security import (
    SECRET_KEY,
    JWT_ALGORITHM,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)


def test_hash_password_roundtrip():
    hashed = hash_password("Str0ngPass!")
    assert hashed != "Str0ngPass!"
    assert verify_password("Str0ngPass!", hashed) is True


def test_verify_password_rejects_wrong_password():
    hashed = hash_password("Str0ngPass!")
    assert verify_password("WrongPass!", hashed) is False


def test_create_access_token_has_type_access():
    token = create_access_token("user-123")
    payload = decode_token(token)
    assert payload["sub"] == "user-123"
    assert payload["type"] == "access"


def test_create_refresh_token_has_type_refresh():
    token = create_refresh_token("user-123")
    payload = decode_token(token)
    assert payload["type"] == "refresh"


def test_decode_token_rejects_expired_token():
    expired_payload = {
        "sub": "user-123",
        "type": "access",
        "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
    }
    expired_token = jwt.encode(expired_payload, SECRET_KEY, algorithm=JWT_ALGORITHM)
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_token(expired_token)
