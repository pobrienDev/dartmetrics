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


# --- Visit recording ------------------------------------------------------

T20 = {"segment": 20, "multiplier": "triple"}
T19 = {"segment": 19, "multiplier": "triple"}
D12 = {"segment": 12, "multiplier": "double"}
S20 = {"segment": 20, "multiplier": "single"}


def make_match(client, setup, best_of=1) -> dict:
    return client.post(
        "/api/v1/matches",
        json={"opponent_player_id": setup["guest"]["id"], "best_of_legs": best_of},
        headers=setup["headers"],
    ).json()


def visit(client, setup, match_id, player_id, darts, expect=201):
    response = client.post(
        f"/api/v1/matches/{match_id}/visits",
        json={"player_id": player_id, "darts": darts},
        headers=setup["headers"],
    )
    assert response.status_code == expect, response.text
    return response.json()


def test_nine_dart_match_over_http(client, setup):
    match = make_match(client, setup, best_of=1)
    own, guest = setup["own"]["id"], setup["guest"]["id"]

    body = visit(client, setup, match["id"], own, [T20] * 3)
    assert body["turn"]["points_scored"] == 180
    me_state = [p for p in body["state"]["players"] if p["player_id"] == own][0]
    assert me_state["remaining_score"] == 321
    assert not me_state["is_active_turn"]  # turn passed to the guest

    visit(client, setup, match["id"], guest, [S20] * 3)
    visit(client, setup, match["id"], own, [T20] * 3)          # 141 left
    visit(client, setup, match["id"], guest, [S20] * 3)
    final = visit(client, setup, match["id"], own, [T20, T19, D12])

    assert final["turn"]["is_checkout"] is True
    assert final["state"]["status"] == "completed"
    assert final["state"]["winner_player_id"] == own
    assert final["state"]["current_leg"] is None
    winner = [p for p in final["state"]["players"] if p["player_id"] == own][0]
    assert winner["legs_won"] == 1


def test_bust_leaves_scoreboard_unchanged(client, setup):
    match = make_match(client, setup)
    own, guest = setup["own"]["id"], setup["guest"]["id"]

    visit(client, setup, match["id"], own, [T20] * 3)   # 321
    visit(client, setup, match["id"], guest, [S20] * 3)
    visit(client, setup, match["id"], own, [T20] * 3)   # 141
    visit(client, setup, match["id"], guest, [S20] * 3)
    # 141 left: T20, T20 busts (below zero on dart 2 leaves 21... no:
    # 141-60-60=21, fine; third dart T20 goes below zero)
    body = visit(client, setup, match["id"], own, [T20, T20, {"segment": 7, "multiplier": "triple"}])

    assert body["turn"]["is_bust"] is True
    me_state = [p for p in body["state"]["players"] if p["player_id"] == own][0]
    assert me_state["remaining_score"] == 141  # restored
    assert not me_state["is_active_turn"]


def test_winning_a_leg_starts_next_with_alternated_starter(client, setup):
    match = make_match(client, setup, best_of=3)
    own, guest = setup["own"]["id"], setup["guest"]["id"]
    assert match["current_leg"]["starting_player_id"] == own

    visit(client, setup, match["id"], own, [T20] * 3)
    visit(client, setup, match["id"], guest, [S20] * 3)
    visit(client, setup, match["id"], own, [T20] * 3)
    visit(client, setup, match["id"], guest, [S20] * 3)
    body = visit(client, setup, match["id"], own, [T20, T19, D12])

    state = body["state"]
    assert state["status"] == "in_progress"
    assert state["current_leg"]["leg_number"] == 2
    assert state["current_leg"]["starting_player_id"] == guest  # alternated
    for player in state["players"]:
        assert player["remaining_score"] == 501  # fresh leg
    own_state = [p for p in state["players"] if p["player_id"] == own][0]
    assert own_state["legs_won"] == 1
    guest_state = [p for p in state["players"] if p["player_id"] == guest][0]
    assert guest_state["is_active_turn"]


def test_out_of_turn_visit_rejected(client, setup):
    match = make_match(client, setup)
    body = visit(client, setup, match["id"], setup["guest"]["id"], [T20] * 3, expect=409)
    assert body["error"]["code"] == "NOT_PLAYER_TURN"


def test_non_participant_cannot_score(client, setup):
    match = make_match(client, setup)
    outsider_headers = signup(client, "outsider@example.com", "Outsider")
    response = client.post(
        f"/api/v1/matches/{match['id']}/visits",
        json={"player_id": setup["own"]["id"], "darts": [T20] * 3},
        headers=outsider_headers,
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "MATCH_ACCESS_DENIED"


def test_impossible_dart_is_422(client, setup):
    match = make_match(client, setup)
    visit(
        client, setup, match["id"], setup["own"]["id"],
        [{"segment": 25, "multiplier": "triple"}], expect=422,
    )
    visit(
        client, setup, match["id"], setup["own"]["id"],
        [{"segment": 21, "multiplier": "single"}], expect=422,
    )


def test_four_darts_is_422(client, setup):
    match = make_match(client, setup)
    visit(client, setup, match["id"], setup["own"]["id"], [S20] * 4, expect=422)


# --- Undo ------------------------------------------------------------------


def undo(client, setup, match_id, expect=200):
    response = client.delete(
        f"/api/v1/matches/{match_id}/visits/latest", headers=setup["headers"]
    )
    assert response.status_code == expect, response.text
    return response.json()


def test_undo_restores_scoreboard_and_turn(client, setup):
    match = make_match(client, setup)
    own = setup["own"]["id"]

    visit(client, setup, match["id"], own, [T20] * 3)  # 321, guest's turn
    state = undo(client, setup, match["id"])

    me_state = [p for p in state["players"] if p["player_id"] == own][0]
    assert me_state["remaining_score"] == 501
    assert me_state["is_active_turn"] is True  # my turn again

    # Re-scoring after undo works (turn number freed up)
    body = visit(client, setup, match["id"], own, [T19] * 3)
    assert body["turn"]["turn_number"] == 1
    assert body["turn"]["points_scored"] == 171


def test_undo_a_bust_restores_dart_counts(client, setup):
    match = make_match(client, setup)
    own, guest = setup["own"]["id"], setup["guest"]["id"]
    visit(client, setup, match["id"], own, [T20] * 3)
    visit(client, setup, match["id"], guest, [S20] * 3)
    visit(client, setup, match["id"], own, [T20] * 3)     # 141
    visit(client, setup, match["id"], guest, [S20] * 3)
    visit(client, setup, match["id"], own, [T20, T20, {"segment": 7, "multiplier": "triple"}])  # bust

    state = undo(client, setup, match["id"])
    me_state = [p for p in state["players"] if p["player_id"] == own][0]
    assert me_state["remaining_score"] == 141
    assert me_state["is_active_turn"] is True


def test_undo_with_no_visits_is_409(client, setup):
    match = make_match(client, setup)
    body = undo(client, setup, match["id"], expect=409)
    assert body["error"]["code"] == "UNDO_NOT_AVAILABLE"


def test_leg_winning_checkout_is_not_undoable(client, setup):
    """Once a checkout completes a leg, the fresh next leg has no
    visits — the completed leg is immutable (spec 13.4)."""
    match = make_match(client, setup, best_of=3)
    own, guest = setup["own"]["id"], setup["guest"]["id"]
    visit(client, setup, match["id"], own, [T20] * 3)
    visit(client, setup, match["id"], guest, [S20] * 3)
    visit(client, setup, match["id"], own, [T20] * 3)
    visit(client, setup, match["id"], guest, [S20] * 3)
    visit(client, setup, match["id"], own, [T20, T19, D12])  # leg 1 won

    body = undo(client, setup, match["id"], expect=409)
    assert body["error"]["code"] == "UNDO_NOT_AVAILABLE"


def test_non_participant_cannot_undo(client, setup):
    match = make_match(client, setup)
    visit(client, setup, match["id"], setup["own"]["id"], [T20] * 3)
    outsider_headers = signup(client, "outsider@example.com", "Outsider")
    response = client.delete(
        f"/api/v1/matches/{match['id']}/visits/latest", headers=outsider_headers
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "MATCH_ACCESS_DENIED"


def test_scoring_completed_match_is_409(client, setup):
    match = make_match(client, setup, best_of=1)
    own, guest = setup["own"]["id"], setup["guest"]["id"]
    visit(client, setup, match["id"], own, [T20] * 3)
    visit(client, setup, match["id"], guest, [S20] * 3)
    visit(client, setup, match["id"], own, [T20] * 3)
    visit(client, setup, match["id"], guest, [S20] * 3)
    visit(client, setup, match["id"], own, [T20, T19, D12])  # match over

    body = visit(client, setup, match["id"], guest, [S20] * 3, expect=409)
    assert body["error"]["code"] == "MATCH_NOT_ACTIVE"
