"""Application settings (dev plan sections 9, 12).

All configuration comes from environment variables, loaded from the
repo-root .env in development. pydantic-settings validates types at
startup, so a missing or malformed value fails loudly and immediately
instead of surfacing as a confusing error mid-request.
"""

from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


def normalize_database_url(url: str) -> str:
    """Pin the psycopg (v3) driver onto a plain PostgreSQL URL.

    Managed databases (Render, Heroku-style) hand out
    ``postgres://`` or ``postgresql://`` connection strings. SQLAlchemy
    treats a bare ``postgresql://`` as psycopg2, which is not installed,
    and rejects ``postgres://`` outright. Any URL that already names a
    driver is left alone.
    """
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",  # .env also holds docker-compose vars we don't need
    )

    database_url: str
    secret_key: str  # signs JWTs; generate with secrets.token_urlsafe(32)
    access_token_expire_minutes: int = 60
    app_name: str = "DartMetrics"

    # Browser origins allowed to call the API cross-origin, comma-separated
    # (e.g. "https://dartmetrics.example.com"). Empty = no CORS middleware,
    # which is correct whenever the frontend is served from the same
    # origin as the API (the Vite dev proxy, or one host in production).
    cors_origins: str = ""

    # Per-client limit on the credential endpoints (login/register), in
    # slowapi notation. Argon2 verification is deliberately slow, so these
    # routes are both a brute-force and a CPU-exhaustion target.
    auth_rate_limit: str = "10/minute"
    rate_limit_enabled: bool = True

    # Directory holding the production frontend build (Vite's dist/).
    # When set and present, the API also serves the single-page app, so
    # one container answers both / and /api. Empty in development, where
    # the Vite dev server serves the app and proxies /api here.
    static_dir: str = ""

    @field_validator("database_url")
    @classmethod
    def database_url_names_driver(cls, value: str) -> str:
        return normalize_database_url(value)

    @field_validator("secret_key")
    @classmethod
    def secret_key_must_be_real(cls, value: str) -> str:
        """Refuse to start with the .env.example placeholder or a short
        key: every token would be forgeable by anyone who read the repo."""
        if value.startswith("change-me") or len(value) < 32:
            raise ValueError(
                "SECRET_KEY must be a random value of at least 32 characters; "
                'generate one with: python -c "import secrets; '
                'print(secrets.token_urlsafe(32))"'
            )
        return value

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def static_path(self) -> Path | None:
        """The frontend build directory, or None when not serving one."""
        if not self.static_dir:
            return None
        path = Path(self.static_dir)
        return path if (path / "index.html").is_file() else None


@lru_cache
def get_settings() -> Settings:
    """Cached accessor so the .env file is read once per process."""
    return Settings()
