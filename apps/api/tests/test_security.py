from datetime import UTC, datetime, timedelta

import jwt
import pytest

from src.config import settings
from src.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_password_hash_is_verifiable():
    hashed = hash_password("correct horse")

    assert hashed != "correct horse"
    assert verify_password("correct horse", hashed) is True
    assert verify_password("battery staple", hashed) is False


@pytest.mark.parametrize("password", ["", "a" * 200])
def test_password_hashes_any_input(password):
    hashed = hash_password(password)

    assert verify_password(password, hashed) is True


def test_create_and_decode_token_roundtrip():
    subject = "3b6e7b4e-2c1a-4f6e-9c1a-000000000001"

    token = create_access_token(subject=subject)
    payload = decode_access_token(token)

    assert payload["sub"] == subject
    assert "exp" in payload


def test_decode_rejects_expired_token():
    expired = jwt.encode(
        {
            "sub": "3b6e7b4e-2c1a-4f6e-9c1a-000000000001",
            "exp": datetime.now(UTC) - timedelta(hours=1),
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )

    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token(expired)


def test_decode_rejects_tampered_token():
    valid = create_access_token(subject="3b6e7b4e-2c1a-4f6e-9c1a-000000000001")

    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token(valid + "tampered")
