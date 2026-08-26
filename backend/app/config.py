"""Application settings (dev plan sections 9, 12).

All configuration comes from environment variables, loaded from the
repo-root .env in development. pydantic-settings validates types at
startup, so a missing or malformed value fails loudly and immediately
instead of surfacing as a confusing error mid-request.
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",  # .env also holds docker-compose vars we don't need
    )

    database_url: str
    app_name: str = "DartMetrics"
    debug: bool = False


@lru_cache
def get_settings() -> Settings:
    """Cached accessor so the .env file is read once per process."""
    return Settings()
