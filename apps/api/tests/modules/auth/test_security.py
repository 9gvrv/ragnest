from datetime import timedelta

from app.modules.auth.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_password_hash_roundtrip():
    hashed = hash_password("supersecret")
    assert hashed != "supersecret"
    assert verify_password("supersecret", hashed) is True


def test_verify_password_rejects_wrong_password():
    hashed = hash_password("supersecret")
    assert verify_password("wrong", hashed) is False


def test_password_hash_roundtrip_for_long_unicode_password():
    password = "pässwörd-" + "x" * 200
    hashed = hash_password(password)
    assert verify_password(password, hashed) is True


def test_access_token_roundtrip_returns_subject():
    token = create_access_token("user-123")
    assert decode_access_token(token) == "user-123"


def test_decode_access_token_rejects_tampered_token():
    token = create_access_token("user-123")
    assert decode_access_token(token + "x") is None


def test_decode_access_token_rejects_expired_token():
    token = create_access_token("user-123", expires_delta=timedelta(seconds=-1))
    assert decode_access_token(token) is None
