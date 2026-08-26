"""Integration tests for match creation and state retrieval."""

import uuid

import pytest


def signup(client, email: str, display_name: str) -> dict:
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
def setup(client):
    """Registered user with a player profile and a guest opponent."""
    headers = signup(client, "pat@example.com", "Patrick")
    own = client.post(
        "/api/v1/players", json={"display_name": "Patrick"}, headers=headers
    ).json()
    guest = client.post(
        "/api/v1/players",
        json={"display_name": "Guest Gary", "is_guest": True},
        headers=headers,
    ).json()
    return {"headers": headers, "own": own, "guest": guest}


def test_create_match_starts_leg_one_at_501(client, setup):
    response = client.post(
        "/api/v1/matches",
        json={"opponent_player_id": setup["guest"]["id"], "best_of_legs": 3},
        headers=setup["headers"],
    )
    assert response.status_code == 201
    state = response.json()

    assert state["status"] == "in_progress"
    assert state["legs_required_to_win"] == 2
    assert state["winner_player_id"] is None
    assert state["current_leg"]["leg_number"] == 1
    assert state["current_leg"]["status"] == "in_progress"
    # Creator starts by default and both players stand at 501
    assert state["current_leg"]["starting_player_id"] == setup["own"]["id"]
    for player in state["players"]:
        assert player["remaining_score"] == 501
        assert player["legs_won"] == 0
    active = [p for p in state["players"] if p["is_active_turn"]]
    assert [p["player_id"] for p in active] == [setup["own"]["id"]]


def test_opponent_can_be_chosen_as_starter(client, setup):
    response = client.post(
        "/api/v1/matches",
        json={
            "opponent_player_id": setup["guest"]["id"],
            "best_of_legs": 1,
            "starting_player_id": setup["guest"]["id"],
        },
        headers=setup["headers"],
    )
    assert response.status_code == 201
    state = response.json()
    assert state["current_leg"]["starting_player_id"] == setup["guest"]["id"]
    active = [p for p in state["players"] if p["is_active_turn"]]
    assert [p["player_id"] for p in active] == [setup["guest"]["id"]]


def test_get_match_returns_same_state(client, setup):
    created = client.post(
        "/api/v1/matches",
        json={"opponent_player_id": setup["guest"]["id"], "best_of_legs": 3},
        headers=setup["headers"],
    ).json()
    fetched = client.get(f"/api/v1/matches/{created['id']}", headers=setup["headers"])
    assert fetched.status_code == 200
    assert fetched.json() == created


def test_match_requires_player_profile(client):
    headers = signup(client, "noplayer@example.com", "NoPlayer")
    response = client.post(
        "/api/v1/matches",
        json={"opponent_player_id": str(uuid.uuid4()), "best_of_legs": 3},
        headers=headers,
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "PLAYER_PROFILE_REQUIRED"


def test_unknown_opponent_is_404(client, setup):
    response = client.post(
        "/api/v1/matches",
        json={"opponent_player_id": str(uuid.uuid4()), "best_of_legs": 3},
        headers=setup["headers"],
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "PLAYER_NOT_FOUND"


def test_cannot_play_yourself(client, setup):
    response = client.post(
        "/api/v1/matches",
        json={"opponent_player_id": setup["own"]["id"], "best_of_legs": 3},
        headers=setup["headers"],
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_MATCH_SETUP"


def test_starter_must_be_a_participant(client, setup):
    outsider = client.post(
        "/api/v1/players",
        json={"display_name": "Bystander Bob", "is_guest": True},
        headers=setup["headers"],
    ).json()
    response = client.post(
        "/api/v1/matches",
        json={
            "opponent_player_id": setup["guest"]["id"],
            "best_of_legs": 3,
            "starting_player_id": outsider["id"],
        },
        headers=setup["headers"],
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_MATCH_SETUP"


def test_even_best_of_legs_rejected_by_validation(client, setup):
    response = client.post(
        "/api/v1/matches",
        json={"opponent_player_id": setup["guest"]["id"], "best_of_legs": 2},
        headers=setup["headers"],
    )
    assert response.status_code == 422


def test_unknown_match_is_404(client, setup):
    response = client.get(f"/api/v1/matches/{uuid.uuid4()}", headers=setup["headers"])
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "MATCH_NOT_FOUND"


def test_matches_require_authentication(client):
    assert (
        client.post(
            "/api/v1/matches",
            json={"opponent_player_id": str(uuid.uuid4()), "best_of_legs": 3},
        ).status_code
        == 401
    )
