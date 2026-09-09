"""Startup configuration guards, CORS wiring, and production static serving."""

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.config import Settings, get_settings, normalize_database_url
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


# --- Managed-database connection strings -----------------------------------


@pytest.mark.parametrize(
    "given",
    [
        "postgres://u:p@host:5432/db",
        "postgresql://u:p@host:5432/db",
        "postgresql+psycopg://u:p@host:5432/db",
    ],
)
def test_database_url_always_names_the_psycopg_driver(given):
    assert normalize_database_url(given) == "postgresql+psycopg://u:p@host:5432/db"
    assert _settings(database_url=given).database_url == "postgresql+psycopg://u:p@host:5432/db"


def test_neon_style_url_keeps_its_query_string():
    neon = "postgresql://u:p@ep-x.eu-central-1.aws.neon.tech/db?sslmode=require&channel_binding=require"
    assert normalize_database_url(neon) == (
        "postgresql+psycopg://u:p@ep-x.eu-central-1.aws.neon.tech/db"
        "?sslmode=require&channel_binding=require"
    )


def test_non_postgres_urls_are_left_alone():
    assert normalize_database_url("sqlite:///x.db") == "sqlite:///x.db"


# --- Serving the frontend build from the API container ---------------------


@pytest.fixture
def frontend_build(tmp_path):
    """A stand-in for Vite's dist/: index.html, a hashed bundle, a favicon."""
    (tmp_path / "index.html").write_text("<!doctype html><div id=root></div>")
    (tmp_path / "favicon.svg").write_text("<svg/>")
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "index-abc123.js").write_text("console.log(1)")
    return tmp_path


def test_no_frontend_served_without_static_dir(app_with_env):
    client = TestClient(app_with_env(STATIC_DIR=""))
    assert client.get("/").status_code == 404
    assert client.get("/api/v1/health").status_code == 200


def test_static_dir_without_a_build_is_ignored(app_with_env, tmp_path):
    client = TestClient(app_with_env(STATIC_DIR=str(tmp_path)))
    assert client.get("/").status_code == 404


def test_frontend_build_is_served_alongside_the_api(app_with_env, frontend_build):
    client = TestClient(app_with_env(STATIC_DIR=str(frontend_build)))

    root = client.get("/")
    assert root.status_code == 200
    assert 'id=root' in root.text
    assert root.headers["cache-control"] == "no-cache"

    # Deep links belong to React Router: refresh on /matches/<id> must work.
    deep = client.get("/matches/1234")
    assert deep.status_code == 200
    assert deep.text == root.text

    bundle = client.get("/assets/index-abc123.js")
    assert bundle.status_code == 200
    assert bundle.text == "console.log(1)"
    assert "immutable" in bundle.headers["cache-control"]

    assert client.get("/favicon.svg").text == "<svg/>"

    # The API keeps precedence, and unknown API paths stay 404s.
    assert client.get("/api/v1/health").json() == {"status": "ok"}
    assert client.get("/api/v1/does-not-exist").status_code == 404
    assert client.get("/api").status_code == 404
    assert client.get("/docs").status_code == 200


def test_frontend_serving_never_escapes_the_build_directory(app_with_env, frontend_build):
    client = TestClient(app_with_env(STATIC_DIR=str(frontend_build)))
    response = client.get("/../pyproject.toml")
    assert response.status_code == 200
    assert 'id=root' in response.text  # fell back to the app shell
