from urllib.parse import parse_qs, urlparse

import pytest
from pydantic import ValidationError

from app.core.config import Settings

NEON = (
    "postgresql://u:p@host/db"
    "?sslmode=require&channel_binding=require&application_name=ragnest"
)


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
