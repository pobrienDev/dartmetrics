"""Rate limiting on the credential endpoints.

The shared `client` fixture disables the limiter (every test logs in);
these tests re-enable it explicitly.
"""

import pytest

from app.config import get_settings


@pytest.fixture
def limited_client(client):
    client.app.state.limiter.enabled = True
    client.app.state.limiter.reset()
    yield client
    client.app.state.limiter.enabled = False


def _limit_count() -> int:
    return int(get_settings().auth_rate_limit.split("/")[0])


def test_login_is_rate_limited_per_client(limited_client):
    body = {"email": "nobody@example.com", "password": "definitely wrong"}
    for _ in range(_limit_count()):
        response = limited_client.post("/api/v1/auth/login", json=body)
        assert response.status_code == 401

    response = limited_client.post("/api/v1/auth/login", json=body)
    assert response.status_code == 429
    assert response.json() == {
        "error": {
            "code": "RATE_LIMITED",
            "message": "Too many attempts; please wait a minute and try again.",
        }
    }
    assert response.headers["Retry-After"] == "60"


def test_register_is_rate_limited_per_client(limited_client):
    for i in range(_limit_count()):
        response = limited_client.post(
            "/api/v1/auth/register",
            json={
                "email": f"burst{i}@example.com",
                "password": "correct horse battery staple",
                "display_name": "Burst",
            },
        )
        assert response.status_code == 201

    response = limited_client.post(
        "/api/v1/auth/register",
        json={
            "email": "burst-extra@example.com",
            "password": "correct horse battery staple",
            "display_name": "Burst",
        },
    )
    assert response.status_code == 429
    assert response.json()["error"]["code"] == "RATE_LIMITED"


def test_rate_limit_does_not_touch_other_routes(limited_client):
    for _ in range(_limit_count() + 5):
        assert limited_client.get("/api/v1/health").status_code == 200
