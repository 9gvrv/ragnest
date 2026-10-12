from functools import lru_cache
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent

_LIBPQ_ONLY_PARAMS = {"sslmode", "channel_binding", "sslnegotiation"}


class Settings(BaseSettings):
    app_name: str = "Ragnest API"
    environment: str = "development"
    debug: bool = False

    neon_db: str

    jwt_secret: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def database_url(self) -> str:
        """Neon URL normalized to the SQLAlchemy asyncpg driver.

        asyncpg rejects libpq-only query params (``sslmode``,
        ``channel_binding``), so they are stripped here and translated into
        ``database_connect_args`` below.
        """
        url = self.neon_db
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)

        parts = urlsplit(url)
        query = [
            (key, value)
            for key, value in parse_qsl(parts.query)
            if key not in _LIBPQ_ONLY_PARAMS
        ]
        return urlunsplit(
            (parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment)
        )

    @property
    def database_connect_args(self) -> dict:
        """Connection kwargs required by Neon's pooled endpoint."""
        query = dict(parse_qsl(urlsplit(self.neon_db).query))
        args: dict = {"ssl": query.get("sslmode") or "require"}
        # Neon's PgBouncer pooler does not support prepared statement caching.
        args["statement_cache_size"] = 0
        return args


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


settings = get_settings()
