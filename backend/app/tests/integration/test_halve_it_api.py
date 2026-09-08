"""Integration tests: Halve It matches over the API."""

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


MISS = {"segment": None, "multiplier": "miss"}
INNER_BULL = {"segment": 25, "multiplier": "double"}


def outer(n):
    return {"segment": n, "multiplier": "single", "band": "outer"}


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


def make_match(client, setup) -> dict:
    response = client.post(
        "/api/v1/matches",
        json={
            "opponent_player_id": setup["guest"]["id"],
            "best_of_legs": 1,
            "game_type": "halve_it",
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


def player_of(state, player_id):
    return next(p for p in state["players"] if p["player_id"] == player_id)


def test_match_starts_at_round_one_outer_black(client, setup):
    match = make_match(client, setup)
    assert match["game_type"] == "halve_it"
    for player in match["players"]:
        assert player["remaining_score"] is None
        assert player["score"] == 40  # house rule: everyone starts on 40
        assert player["round"] == 1
        assert player["round_target"] == "outer_black"


def test_scoring_round_adds_face_value_and_advances(client, setup):
    match = make_match(client, setup)
    own = setup["own"]["id"]

    body = visit(client, setup, match["id"], own, [outer(20), outer(1), MISS])
    me = player_of(body["state"], own)
    assert me["score"] == 60  # 40 + 20; the 1 is white
    assert me["round"] == 2
    assert me["round_target"] == "outer_white"

    # Opponent is still on round 1
    guest_state = player_of(body["state"], setup["guest"]["id"])
    assert guest_state["round"] == 1
    assert guest_state["is_active_turn"]


def test_missed_round_halves_rounding_up(client, setup):
    match = make_match(client, setup)
    own, guest = setup["own"]["id"], setup["guest"]["id"]

    visit(client, setup, match["id"], own, [outer(20), outer(13), outer(12)])  # 85
    visit(client, setup, match["id"], guest, [MISS, MISS, MISS])  # halve 40 -> 20
    body = visit(client, setup, match["id"], own, [MISS, MISS, MISS])  # round 2 miss
    assert player_of(body["state"], own)["score"] == 43  # 85 halved up


def test_band_on_a_double_is_rejected(client, setup):
    match = make_match(client, setup)
    visit(
        client,
        setup,
        match["id"],
        setup["own"]["id"],
        [{"segment": 20, "multiplier": "double", "band": "outer"}, MISS, MISS],
        expect=422,
    )


def test_wrong_dart_count_is_rejected(client, setup):
    match = make_match(client, setup)
    body = visit(
        client, setup, match["id"], setup["own"]["id"], [outer(20)], expect=400
    )
    assert body["error"]["code"] == "INVALID_TURN"


def play_out_match(client, setup, match_id):
    """Both miss rounds 1-8 (40 halves down to 1 for each); P1 lands a
    red bull in round 9 to finish 51-1."""
    own, guest = setup["own"]["id"], setup["guest"]["id"]
    for _ in range(8):  # rounds 1-8
        visit(client, setup, match_id, own, [MISS, MISS, MISS])
        visit(client, setup, match_id, guest, [MISS, MISS, MISS])
    visit(client, setup, match_id, own, [INNER_BULL, MISS, MISS])
    visit(client, setup, match_id, guest, [MISS, MISS, MISS])


def test_higher_score_after_nine_rounds_wins(client, setup):
    match = make_match(client, setup)
    own = setup["own"]["id"]
    play_out_match(client, setup, match["id"])

    final = client.get(f"/api/v1/matches/{match['id']}", headers=setup["headers"]).json()
    assert final["status"] == "completed"
    assert final["winner_player_id"] == own
    # 40 halved eight times (rounding up) grinds down to 1, then +50
    assert player_of(final, own)["score"] == 51
    assert player_of(final, setup["guest"]["id"])["score"] == 1


def test_win_can_land_on_the_other_player(client, setup):
    """Gary throws last but Patrick wins — the completion must credit
    the higher score, not the final thrower."""
    match = make_match(client, setup)
    guest = setup["guest"]["id"]
    play_out_match(client, setup, match["id"])

    final = client.get(f"/api/v1/matches/{match['id']}", headers=setup["headers"]).json()
    assert final["winner_player_id"] != guest


def test_tie_after_nine_rounds_goes_to_red_bull_tiebreak(client, setup):
    match = make_match(client, setup)
    own, guest = setup["own"]["id"], setup["guest"]["id"]
    for _ in range(9):  # both miss everything: 40 grinds to a 1-1 tie
        visit(client, setup, match["id"], own, [MISS, MISS, MISS])
        visit(client, setup, match["id"], guest, [MISS, MISS, MISS])

    state = client.get(f"/api/v1/matches/{match['id']}", headers=setup["headers"]).json()
    assert state["status"] == "in_progress"
    assert player_of(state, own)["round"] == 10
    assert player_of(state, own)["round_target"] == "red_bull"

    # Patrick lands a red bull, Gary misses: tie broken 51-1
    visit(client, setup, match["id"], own, [INNER_BULL, MISS, MISS])
    body = visit(client, setup, match["id"], guest, [MISS, MISS, MISS])
    assert body["state"]["status"] == "completed"
    assert body["state"]["winner_player_id"] == own


def test_undo_restores_score_and_round(client, setup):
    match = make_match(client, setup)
    own = setup["own"]["id"]
    visit(client, setup, match["id"], own, [outer(20), outer(13), MISS])  # 73

    response = client.delete(
        f"/api/v1/matches/{match['id']}/visits/latest", headers=setup["headers"]
    )
    assert response.status_code == 200
    me = player_of(response.json(), own)
    assert me["score"] == 40
    assert me["round"] == 1
    assert me["is_active_turn"]

    # Re-throw works and replays cleanly
    body = visit(client, setup, match["id"], own, [outer(10), MISS, MISS])
    assert player_of(body["state"], own)["score"] == 50


def test_halve_it_does_not_pollute_501_statistics(client, setup):
    match = make_match(client, setup)
    play_out_match(client, setup, match["id"])

    stats = client.get(
        f"/api/v1/players/{setup['own']['id']}/stats", headers=setup["headers"]
    ).json()
    assert stats["matches_played"] == 0
    assert stats["total_darts"] == 0