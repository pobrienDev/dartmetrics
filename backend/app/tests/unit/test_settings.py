"""Startup configuration guards and CORS wiring."""

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.config import Settings, get_settings
from app.main import create_app

GOOD_KEY = "x" * 43  # what secrets.token_urlsafe(32) produces, length-wise


def _settings(**overrides) -> Settings:
    base = {"database_url": "postgresql+psycopg://u:p@localhost/db", "secret_key": GOOD_KEY}
    base.update(overrides)
    return Settings(_env_file=None, **base)


def test_placeholder_secret_key_is_rejected():
    with pytest.raises(ValidationError, match="SECRET_KEY must be a random value"):
        _settings(secret_key="change-me-generate-a-real-random-value")


def test_short_secret_key_is_rejected():
    with pytest.raises(ValidationError):
        _settings(secret_key="tooshort")


def test_real_secret_key_is_accepted():
    assert _settings().secret_key == GOOD_KEY


def test_cors_origins_parse_as_trimmed_list():
    settings = _settings(cors_origins=" https://a.example , https://b.example,")
    assert settings.cors_origin_list == ["https://a.example", "https://b.example"]
    assert _settings().cors_origin_list == []


@pytest.fixture
def app_with_env(monkeypatch):
    """Build a fresh app from environment overrides, restoring the cached
    settings afterwards so other tests see the real .env again."""

    def build(**env):
        for key, value in env.items():
            monkeypatch.setenv(key, value)
        get_settings.cache_clear()
        return create_app()

    yield build
    get_settings.cache_clear()


def test_no_cors_headers_by_default(app_with_env):
    client = TestClient(app_with_env(CORS_ORIGINS=""))
    response = client.get("/api/v1/health", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in response.headers


def test_cors_allowlist_is_honoured(app_with_env):
    client = TestClient(app_with_env(CORS_ORIGINS="https://app.example"))

    allowed = client.get("/api/v1/health", headers={"Origin": "https://app.example"})
    assert allowed.headers["access-control-allow-origin"] == "https://app.example"

    denied = client.get("/api/v1/health", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in denied.headers

    preflight = client.options(
        "/api/v1/matches",
        headers={
            "Origin": "https://app.example",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )
    assert preflight.status_code == 200
    assert "POST" in preflight.headers["access-control-allow-methods"]
