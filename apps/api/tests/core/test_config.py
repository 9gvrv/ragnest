from urllib.parse import parse_qs, urlparse

import pytest
from pydantic import ValidationError

from app.core.config import Settings, settings

NEON = "postgresql://u:p@host/db?sslmode=require&channel_binding=require&application_name=ragnest"


def test_rewrites_scheme_and_strips_libpq_only_params():
    s = Settings(DATABASE_URL=NEON)
    parsed = urlparse(s.database_url)
    assert parsed.scheme == "postgresql+asyncpg"
    params = parse_qs(parsed.query)
    assert "sslmode" not in params
    assert "channel_binding" not in params
    assert params.get("application_name") == ["ragnest"]


def test_connect_args_enable_ssl_and_disable_statement_cache():
    s = Settings(DATABASE_URL=NEON)
    assert s.database_connect_args == {"statement_cache_size": 0, "ssl": True}


def test_local_url_does_not_force_ssl():
    s = Settings(DATABASE_URL="postgresql://u:p@localhost:5432/ragnest")
    assert urlparse(s.database_url).scheme == "postgresql+asyncpg"
    assert "ssl" not in s.database_connect_args
    assert s.database_connect_args["statement_cache_size"] == 0


def test_missing_database_url_raises(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_access_token_expiry_defaults_to_30_minutes():
    assert settings.ACCESS_TOKEN_EXPIRE_MINUTES == 30


def test_blank_llm_settings_fall_back_to_defaults():
    s = Settings(DATABASE_URL=NEON, LLM_BASE_URL="", LLM_MODEL="")

    assert s.LLM_BASE_URL == "https://api.groq.com/openai/v1"
    assert s.LLM_MODEL == "openai/gpt-oss-120b"


def test_secret_key_is_loaded():
    assert settings.SECRET_KEY


def test_cors_origins_are_split_trimmed_and_normalized():
    s = Settings(
        DATABASE_URL=NEON,
        CORS_ORIGINS=" https://ragnest.vercel.app , http://localhost:3000/ ",
    )

    assert s.cors_origins == ["https://ragnest.vercel.app", "http://localhost:3000"]


def test_cors_origins_are_empty_by_default():
    s = Settings(DATABASE_URL=NEON, CORS_ORIGINS="")

    assert s.cors_origins == []
