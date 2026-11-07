from pathlib import Path
from urllib.parse import parse_qs, parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "Ragnest API"
    LOG_LEVEL: str = "INFO"
    DATABASE_URL: str
    SECRET_KEY: str
    GEMINI_API: str
    LLM_API_KEY: str
    LLM_BASE_URL: str = "https://api.groq.com/openai/v1"
    LLM_MODEL: str = "openai/gpt-oss-120b"
    LLM_REASONING_EFFORT: str = "low"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    CORS_ORIGINS: str = ""

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[2] / ".env",
        extra="ignore",
    )

    @model_validator(mode="after")
    def _blank_llm_values_use_defaults(self) -> "Settings":
        """An empty key in `.env` must not blank out a working default."""
        self.LLM_BASE_URL = self.LLM_BASE_URL.strip() or "https://api.groq.com/openai/v1"
        self.LLM_MODEL = self.LLM_MODEL.strip() or "openai/gpt-oss-120b"
        self.LLM_REASONING_EFFORT = self.LLM_REASONING_EFFORT.strip()
        return self

    # Changes the URL scheme and removes incompatible parameters.
    @property
    def database_url(self) -> str:
        parsed = urlsplit(self.DATABASE_URL)

        # Replace the scheme
        scheme = "postgresql+asyncpg"

        # Parse query parameters and remove the unwanted ones
        query_params = parse_qsl(parsed.query, keep_blank_values=True)
        excluded = {"sslmode", "channel_binding", "sslnegotiation"}

        filtered_params = [(key, value) for key, value in query_params if key not in excluded]

        # Reconstruct the URL, preserving everything else
        return urlunsplit(
            (
                scheme,
                parsed.netloc,
                parsed.path,
                urlencode(filtered_params),
                parsed.fragment,
            )
        )

    # Builds the driver's connection options from the original URL.
    @property
    def database_connect_args(self) -> dict:
        parsed = urlsplit(self.DATABASE_URL)
        query_params = parse_qs(parsed.query)

        connect_args = {"statement_cache_size": 0}

        if query_params.get("sslmode", [None])[0] == "require":
            connect_args["ssl"] = True

        return connect_args

    # Comma-separated browser origins. An empty value disables CORS entirely.
    @property
    def cors_origins(self) -> list[str]:
        return [
            origin.strip().rstrip("/") for origin in self.CORS_ORIGINS.split(",") if origin.strip()
        ]


settings = Settings()
