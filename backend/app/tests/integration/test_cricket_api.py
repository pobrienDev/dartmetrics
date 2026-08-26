"""Integration tests: Cricket matches over the API."""

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


T = lambda n: {"segment": n, "multiplier": "triple"}  # noqa: E731
S = lambda n: {"segment": n, "multiplier": "single"}  # noqa: E731
INNER_BULL = {"segment": 25, "multiplier": "double"}
OUTER_BULL = {"segment": 25, "multiplier": "single"}
MISS = {"segment": None, "multiplier": "miss"}


@pytest.fixture
def setup(client):
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


def make_cricket_match(client, setup, best_of=1) -> dict:
    response = client.post(
        "/api/v1/matches",
        json={
            "opponent_player_id": setup["guest"]["id"],
            "best_of_legs": best_of,
            "game_type": "cricket",
        },
        headers=setup["headers"],
    )
    assert response.status_code == 201, response.text
    return response.json()


def visit(client, setup, match_id, player_id, darts, expect=201):
    response = client.post(
        f"/api/v1/matches/{match_id}/visits",
        json={"player_id": player_id, "darts": darts},
        headers=setup["headers"],
    )
    assert response.status_code == expect, response.text
    return response.json()


def marks_of(state, player_id):
    return next(p for p in state["players"] if p["player_id"] == player_id)["marks"]


def test_cricket_match_starts_with_open_board(client, setup):
    match = make_cricket_match(client, setup)
    assert match["game_type"] == "cricket"
    for player in match["players"]:
        assert player["remaining_score"] is None
        assert player["marks"] == {str(t): 0 for t in (15, 16, 17, 18, 19, 20, 25)}


def test_visit_updates_marks_and_passes_turn(client, setup):
    match = make_cricket_match(client, setup)
    own = setup["own"]["id"]

    body = visit(client, setup, match["id"], own, [T(20), T(19), S(18)])
    marks = marks_of(body["state"], own)
    assert marks["20"] == 3
    assert marks["19"] == 3
    assert marks["18"] == 1
    assert body["turn"]["points_scored"] == 0  # no-points variant

    active = [p for p in body["state"]["players"] if p["is_active_turn"]]
    assert [p["player_id"] for p in active] == [setup["guest"]["id"]]


def test_closed_targets_and_non_targets_are_inert(client, setup):
    match = make_cricket_match(client, setup)
    own, guest = setup["own"]["id"], setup["guest"]["id"]
    visit(client, setup, match["id"], own, [T(20), T(20), S(14)])
    body = visit(client, setup, match["id"], guest, [MISS, MISS, MISS])
    marks = marks_of(body["state"], own)
    assert marks["20"] == 3  # second T20 and the 14 changed nothing


def test_winning_dart_ends_leg_and_match(client, setup):
    match = make_cricket_match(client, setup, best_of=1)
    own, guest = setup["own"]["id"], setup["guest"]["id"]

    visit(client, setup, match["id"], own, [T(15), T(16), T(17)])
    visit(client, setup, match["id"], guest, [S(15), MISS, MISS])
    visit(client, setup, match["id"], own, [T(18), T(19), T(20)])
    visit(client, setup, match["id"], guest, [S(15), MISS, MISS])
    # Bull: inner (2 marks) then outer (1) wins on dart 2
    final = visit(client, setup, match["id"], own, [INNER_BULL, OUTER_BULL])

    assert final["turn"]["is_checkout"] is True
    assert final["state"]["status"] == "completed"
    assert final["state"]["winner_player_id"] == own


def test_darts_after_winning_dart_are_rejected(client, setup):
    match = make_cricket_match(client, setup)
    own, guest = setup["own"]["id"], setup["guest"]["id"]
    visit(client, setup, match["id"], own, [T(15), T(16), T(17)])
    visit(client, setup, match["id"], guest, [MISS, MISS, MISS])
    visit(client, setup, match["id"], own, [T(18), T(19), T(20)])
    visit(client, setup, match["id"], guest, [MISS, MISS, MISS])

    body = visit(
        client, setup, match["id"], own, [INNER_BULL, OUTER_BULL, S(15)], expect=400
    )
    assert body["error"]["code"] == "INVALID_TURN"


def test_short_visit_without_win_is_rejected(client, setup):
    match = make_cricket_match(client, setup)
    body = visit(
        client, setup, match["id"], setup["own"]["id"], [T(20), T(19)], expect=400
    )
    assert body["error"]["code"] == "INVALID_TURN"


def test_leg_win_starts_next_leg_with_fresh_board(client, setup):
    match = make_cricket_match(client, setup, best_of=3)
    own, guest = setup["own"]["id"], setup["guest"]["id"]
    visit(client, setup, match["id"], own, [T(15), T(16), T(17)])
    visit(client, setup, match["id"], guest, [MISS, MISS, MISS])
    visit(client, setup, match["id"], own, [T(18), T(19), T(20)])
    visit(client, setup, match["id"], guest, [MISS, MISS, MISS])
    body = visit(client, setup, match["id"], own, [INNER_BULL, INNER_BULL])

    state = body["state"]
    assert state["status"] == "in_progress"
    assert state["current_leg"]["leg_number"] == 2
    assert state["current_leg"]["starting_player_id"] == guest
    for player in state["players"]:
        assert all(v == 0 for v in player["marks"].values())


def test_undo_rebuilds_marks_from_raw_darts(client, setup):
    match = make_cricket_match(client, setup)
    own, guest = setup["own"]["id"], setup["guest"]["id"]
    visit(client, setup, match["id"], own, [T(20), S(19), MISS])
    visit(client, setup, match["id"], guest, [S(15), MISS, MISS])
    visit(client, setup, match["id"], own, [T(19), S(20), MISS])

    response = client.delete(
        f"/api/v1/matches/{match['id']}/visits/latest", headers=setup["headers"]
    )
    assert response.status_code == 200
    marks = marks_of(response.json(), own)
    assert marks["20"] == 3
    assert marks["19"] == 1  # second visit's T19 gone again


def test_cricket_does_not_pollute_501_statistics(client, setup):
    match = make_cricket_match(client, setup, best_of=1)
    own, guest = setup["own"]["id"], setup["guest"]["id"]
    visit(client, setup, match["id"], own, [T(15), T(16), T(17)])
    visit(client, setup, match["id"], guest, [MISS, MISS, MISS])
    visit(client, setup, match["id"], own, [T(18), T(19), T(20)])
    visit(client, setup, match["id"], guest, [MISS, MISS, MISS])
    visit(client, setup, match["id"], own, [INNER_BULL, OUTER_BULL])

    stats = client.get(
        f"/api/v1/players/{own}/stats", headers=setup["headers"]
    ).json()
    assert stats["matches_played"] == 0  # completed cricket match excluded
    assert stats["total_darts"] == 0
    assert stats["three_dart_average"] is None