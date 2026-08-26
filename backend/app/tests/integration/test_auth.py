"""Integration tests for registration against real PostgreSQL.

get_db is overridden with the rollback-wrapped test session, so the
endpoint's db.commit() lands in a savepoint that the fixture's outer
rollback still discards — real database behavior, no leftover rows.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.auth.models import User
from app.db import get_db
from app.main import app


@pytest.fixture
def client(db_session):
    # Must be a generator *function* — FastAPI unwraps those into
    # yield-dependencies; a plain callable returning an iterator is not.
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


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
