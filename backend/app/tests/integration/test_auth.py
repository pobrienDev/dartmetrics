"""Integration tests for registration against real PostgreSQL.

get_db is overridden with the rollback-wrapped test session, so the
endpoint's db.commit() lands in a savepoint that the fixture's outer
rollback still discards — real database behavior, no leftover rows.
"""

import pytest
from sqlalchemy import select

from app.auth.models import User


VALID_BODY = {
    "email": "pat@example.com",
    "password": "correct horse battery staple",
    "display_name": "Patrick",
}


def test_register_creates_user(client, db_session):
    response = client.post("/api/v1/auth/register", json=VALID_BODY)
    assert response.status_code == 201

    body = response.json()
    assert body["email"] == "pat@example.com"
    assert body["display_name"] == "Patrick"
    assert body["is_active"] is True
    # No password material may ever appear in a response
    assert "password" not in response.text.lower()

    stored = db_session.scalar(select(User).where(User.email == "pat@example.com"))
    assert stored is not None
    assert stored.password_hash.startswith("$argon2")
    assert stored.password_hash != VALID_BODY["password"]


def test_register_normalizes_email_case(client):
    response = client.post(
        "/api/v1/auth/register", json={**VALID_BODY, "email": "Pat@Example.COM"}
    )
    assert response.status_code == 201
    assert response.json()["email"] == "pat@example.com"


def test_duplicate_email_returns_409_envelope(client):
    assert client.post("/api/v1/auth/register", json=VALID_BODY).status_code == 201
    duplicate = client.post(
        "/api/v1/auth/register",
        json={**VALID_BODY, "email": "PAT@example.com", "display_name": "Impostor"},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "EMAIL_ALREADY_REGISTERED"


@pytest.mark.parametrize(
    "override",
    [
        {"email": "not-an-email"},
        {"password": "short"},
        {"display_name": ""},
    ],
)
def test_invalid_input_is_rejected_with_422(client, override):
    response = client.post("/api/v1/auth/register", json={**VALID_BODY, **override})
    assert response.status_code == 422


def test_login_returns_decodable_token(client, db_session):
    created = client.post("/api/v1/auth/register", json=VALID_BODY).json()
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "Pat@Example.com", "password": VALID_BODY["password"]},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"

    from app.common.security import decode_access_token

    assert str(decode_access_token(body["access_token"])) == created["id"]


@pytest.mark.parametrize(
    "email, password",
    [
        ("pat@example.com", "wrong password entirely"),
        ("nobody@example.com", "correct horse battery staple"),
    ],
)
def test_bad_credentials_get_identical_401(client, email, password):
    client.post("/api/v1/auth/register", json=VALID_BODY)
    response = client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"
    assert response.json()["error"]["message"] == "Incorrect email or password."


def register_and_login(client) -> tuple[dict, dict]:
    """Helper: returns (created user body, auth headers)."""
    created = client.post("/api/v1/auth/register", json=VALID_BODY).json()
    token = client.post(
        "/api/v1/auth/login",
        json={"email": VALID_BODY["email"], "password": VALID_BODY["password"]},
    ).json()["access_token"]
    return created, {"Authorization": f"Bearer {token}"}


def test_me_returns_authenticated_user(client):
    created, headers = register_and_login(client)
    response = client.get("/api/v1/me", headers=headers)
    assert response.status_code == 200
    assert response.json()["id"] == created["id"]
    assert response.json()["email"] == "pat@example.com"


@pytest.mark.parametrize(
    "headers",
    [
        {},                                            # no header at all
        {"Authorization": "Bearer not.a.token"},       # garbage token
        {"Authorization": "Basic cGF0OnB3"},           # wrong scheme
    ],
)
def test_me_rejects_unauthenticated_requests(client, headers):
    response = client.get("/api/v1/me", headers=headers)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "NOT_AUTHENTICATED"
    assert response.headers.get("WWW-Authenticate") == "Bearer"


def test_me_rejects_token_for_nonexistent_user(client):
    import uuid

    from app.common.security import create_access_token

    ghost_headers = {"Authorization": f"Bearer {create_access_token(uuid.uuid4())}"}
    response = client.get("/api/v1/me", headers=ghost_headers)
    assert response.status_code == 401


def test_me_rejects_deactivated_user_with_valid_token(client, db_session):
    created, headers = register_and_login(client)
    user = db_session.scalar(select(User).where(User.email == "pat@example.com"))
    user.is_active = False
    db_session.flush()

    response = client.get("/api/v1/me", headers=headers)
    assert response.status_code == 401


def test_deactivated_account_cannot_login(client, db_session):
    client.post("/api/v1/auth/register", json=VALID_BODY)
    user = db_session.scalar(select(User).where(User.email == "pat@example.com"))
    user.is_active = False
    db_session.flush()

    response = client.post(
        "/api/v1/auth/login",
        json={"email": VALID_BODY["email"], "password": VALID_BODY["password"]},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"
