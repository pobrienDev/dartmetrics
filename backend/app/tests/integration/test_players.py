"""Integration tests for player profile endpoints."""

import uuid

import pytest


def signup(client, email: str, display_name: str) -> dict:
    """Register + login; returns auth headers."""
    client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "correct horse battery staple",
            "display_name": display_name,
        },
    )
    token = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "correct horse battery staple"},
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def headers(client):
    return signup(client, "pat@example.com", "Patrick")


def test_create_own_player_profile(client, headers):
    response = client.post(
        "/api/v1/players",
        json={"display_name": "Patrick", "nickname": "The Machine"},
        headers=headers,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["display_name"] == "Patrick"
    assert body["nickname"] == "The Machine"
    assert body["user_id"] is not None

    me = client.get("/api/v1/me", headers=headers).json()
    assert body["user_id"] == me["id"]


def test_second_own_profile_is_rejected(client, headers):
    assert (
        client.post(
            "/api/v1/players", json={"display_name": "Patrick"}, headers=headers
        ).status_code
        == 201
    )
    duplicate = client.post(
        "/api/v1/players", json={"display_name": "Patrick II"}, headers=headers
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "PLAYER_PROFILE_EXISTS"


def test_guests_are_unlinked_and_unlimited(client, headers):
    client.post("/api/v1/players", json={"display_name": "Patrick"}, headers=headers)
    for name in ("Guest Gary", "Guest Gina"):
        response = client.post(
            "/api/v1/players",
            json={"display_name": name, "is_guest": True},
            headers=headers,
        )
        assert response.status_code == 201
        assert response.json()["user_id"] is None


def test_get_player_visible_to_other_users(client, headers):
    created = client.post(
        "/api/v1/players", json={"display_name": "Patrick"}, headers=headers
    ).json()
    other_headers = signup(client, "other@example.com", "Other")
    response = client.get(f"/api/v1/players/{created['id']}", headers=other_headers)
    assert response.status_code == 200
    assert response.json()["display_name"] == "Patrick"


def test_get_unknown_player_returns_404(client, headers):
    response = client.get(f"/api/v1/players/{uuid.uuid4()}", headers=headers)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "PLAYER_NOT_FOUND"


def test_update_own_player(client, headers):
    created = client.post(
        "/api/v1/players", json={"display_name": "Patrick"}, headers=headers
    ).json()
    response = client.patch(
        f"/api/v1/players/{created['id']}",
        json={"nickname": "180 Machine"},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["nickname"] == "180 Machine"
    assert response.json()["display_name"] == "Patrick"  # untouched


def test_cannot_update_someone_elses_player(client, headers):
    created = client.post(
        "/api/v1/players", json={"display_name": "Patrick"}, headers=headers
    ).json()
    other_headers = signup(client, "other@example.com", "Other")
    response = client.patch(
        f"/api/v1/players/{created['id']}",
        json={"display_name": "Hijacked"},
        headers=other_headers,
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_players_require_authentication(client):
    assert client.post("/api/v1/players", json={"display_name": "X"}).status_code == 401
    assert client.get(f"/api/v1/players/{uuid.uuid4()}").status_code == 401


def test_empty_display_name_rejected(client, headers):
    response = client.post(
        "/api/v1/players", json={"display_name": ""}, headers=headers
    )
    assert response.status_code == 422
