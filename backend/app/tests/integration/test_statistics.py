"""Integration tests for player statistics.

The scripted match: Patrick's nine-darter (180, 180, 141-out) against
Guest Gary's steady single-20s gives hand-checkable expected values.
"""

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


T20 = {"segment": 20, "multiplier": "triple"}
T19 = {"segment": 19, "multiplier": "triple"}
D12 = {"segment": 12, "multiplier": "double"}
S20 = {"segment": 20, "multiplier": "single"}


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


def play_nine_darter(client, setup) -> str:
    match = client.post(
        "/api/v1/matches",
        json={"opponent_player_id": setup["guest"]["id"], "best_of_legs": 1},
        headers=setup["headers"],
    ).json()
    own, guest = setup["own"]["id"], setup["guest"]["id"]
    for player, darts in [
        (own, [T20] * 3),
        (guest, [S20] * 3),
        (own, [T20] * 3),
        (guest, [S20] * 3),
        (own, [T20, T19, D12]),
    ]:
        response = client.post(
            f"/api/v1/matches/{match['id']}/visits",
            json={"player_id": player, "darts": darts},
            headers=setup["headers"],
        )
        assert response.status_code == 201, response.text
    return match["id"]


def get_stats(client, setup, player_id) -> dict:
    response = client.get(
        f"/api/v1/players/{player_id}/stats", headers=setup["headers"]
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_stats_after_nine_darter(client, setup):
    play_nine_darter(client, setup)
    stats = get_stats(client, setup, setup["own"]["id"])

    assert stats["matches_played"] == 1
    assert stats["matches_won"] == 1
    assert stats["win_percentage"] == 100.0
    assert stats["legs_played"] == 1
    assert stats["legs_won"] == 1
    assert stats["best_leg_darts"] == 9

    assert stats["total_darts"] == 9
    # 501 points over 9 darts -> (501/9)*3 = 167.0
    assert stats["three_dart_average"] == 167.0
    assert stats["first_nine_average"] == 167.0

    assert stats["highest_visit"] == 180
    assert stats["count_180"] == 2
    assert stats["count_140_plus"] == 1  # the 141 checkout visit
    assert stats["count_100_plus"] == 0

    # Only the final dart was thrown from a finishable score (24)
    assert stats["checkout_attempts"] == 1
    assert stats["checkout_successes"] == 1
    assert stats["checkout_percentage"] == 100.0


def test_stats_for_the_losing_guest(client, setup):
    play_nine_darter(client, setup)
    stats = get_stats(client, setup, setup["guest"]["id"])

    assert stats["matches_played"] == 1
    assert stats["matches_won"] == 0
    assert stats["win_percentage"] == 0.0
    assert stats["legs_won"] == 0
    assert stats["best_leg_darts"] is None

    # Two visits of S20 x3: 120 points over 6 darts -> 60.0 average
    assert stats["total_darts"] == 6
    assert stats["three_dart_average"] == 60.0
    # Fewer than 9 darts in the leg: no first-nine sample
    assert stats["first_nine_average"] is None
    assert stats["highest_visit"] == 60
    assert stats["checkout_attempts"] == 0
    assert stats["checkout_percentage"] is None  # N/A, never 0%


def test_bust_darts_count_but_score_zero(client, setup):
    match = client.post(
        "/api/v1/matches",
        json={"opponent_player_id": setup["guest"]["id"], "best_of_legs": 1},
        headers=setup["headers"],
    ).json()
    own, guest = setup["own"]["id"], setup["guest"]["id"]
    for player, darts in [
        (own, [T20] * 3),                                    # 321
        (guest, [S20] * 3),
        (own, [T20] * 3),                                    # 141
        (guest, [S20] * 3),
        (own, [T20, T20, {"segment": 7, "multiplier": "triple"}]),  # bust
    ]:
        client.post(
            f"/api/v1/matches/{match['id']}/visits",
            json={"player_id": player, "darts": darts},
            headers=setup["headers"],
        )

    stats = get_stats(client, setup, own)
    # 360 effective points over 9 darts (bust visit scored 0)
    assert stats["total_darts"] == 9
    assert stats["three_dart_average"] == 120.0
    assert stats["count_180"] == 2  # the bust 180-pace visit does not count
    assert stats["highest_visit"] == 180
    assert stats["matches_played"] == 0  # match still in progress


def test_empty_dataset_has_no_divisions_by_zero(client, setup):
    stats = get_stats(client, setup, setup["own"]["id"])
    assert stats["matches_played"] == 0
    assert stats["win_percentage"] is None
    assert stats["three_dart_average"] is None
    assert stats["first_nine_average"] is None
    assert stats["highest_visit"] is None
    assert stats["checkout_percentage"] is None
    assert stats["best_leg_darts"] is None
    assert stats["count_180"] == 0


def play_match(client, setup, winner_id, best_of=1):
    """Best-of-1 where winner_id takes the nine-darter."""
    own, guest = setup["own"]["id"], setup["guest"]["id"]
    loser = guest if winner_id == own else own
    match = client.post(
        "/api/v1/matches",
        json={
            "opponent_player_id": guest,
            "best_of_legs": best_of,
            "starting_player_id": winner_id,
        },
        headers=setup["headers"],
    ).json()
    for player, darts in [
        (winner_id, [T20] * 3),
        (loser, [S20] * 3),
        (winner_id, [T20] * 3),
        (loser, [S20] * 3),
        (winner_id, [T20, T19, D12]),
    ]:
        response = client.post(
            f"/api/v1/matches/{match['id']}/visits",
            json={"player_id": player, "darts": darts},
            headers=setup["headers"],
        )
        assert response.status_code == 201, response.text
    return match["id"]


def test_head_to_head_counts_both_directions(client, setup):
    own, guest = setup["own"]["id"], setup["guest"]["id"]
    play_match(client, setup, winner_id=own)
    play_match(client, setup, winner_id=own)
    play_match(client, setup, winner_id=guest)

    body = client.get(
        f"/api/v1/players/{own}/head-to-head/{guest}", headers=setup["headers"]
    ).json()
    assert body["matches_played"] == 3
    assert body["player"]["matches_won"] == 2
    assert body["opponent"]["matches_won"] == 1
    assert body["player"]["legs_won"] == 2
    assert body["opponent"]["legs_won"] == 1
    assert body["last_played_at"] is not None

    # Same data viewed from the guest's side is mirrored
    mirrored = client.get(
        f"/api/v1/players/{guest}/head-to-head/{own}", headers=setup["headers"]
    ).json()
    assert mirrored["player"]["matches_won"] == 1
    assert mirrored["opponent"]["matches_won"] == 2


def test_head_to_head_ignores_matches_in_progress(client, setup):
    own, guest = setup["own"]["id"], setup["guest"]["id"]
    client.post(
        "/api/v1/matches",
        json={"opponent_player_id": guest, "best_of_legs": 3},
        headers=setup["headers"],
    )
    body = client.get(
        f"/api/v1/players/{own}/head-to-head/{guest}", headers=setup["headers"]
    ).json()
    assert body["matches_played"] == 0
    assert body["last_played_at"] is None


def test_head_to_head_with_self_is_400(client, setup):
    own = setup["own"]["id"]
    response = client.get(
        f"/api/v1/players/{own}/head-to-head/{own}", headers=setup["headers"]
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_REQUEST"


def test_head_to_head_unknown_player_is_404(client, setup):
    response = client.get(
        f"/api/v1/players/{setup['own']['id']}/head-to-head/{uuid.uuid4()}",
        headers=setup["headers"],
    )
    assert response.status_code == 404


def test_match_summary_after_nine_darter(client, setup):
    match_id = play_nine_darter(client, setup)
    response = client.get(
        f"/api/v1/matches/{match_id}/summary", headers=setup["headers"]
    )
    assert response.status_code == 200
    body = response.json()

    assert body["status"] == "completed"
    assert body["winner_player_id"] == setup["own"]["id"]

    by_id = {p["player_id"]: p for p in body["players"]}
    winner = by_id[setup["own"]["id"]]
    assert winner["legs_won"] == 1
    assert winner["darts_thrown"] == 9
    assert winner["points_scored"] == 501
    assert winner["three_dart_average"] == 167.0
    assert winner["count_180"] == 2
    assert winner["checkout_percentage"] == 100.0

    loser = by_id[setup["guest"]["id"]]
    assert loser["legs_won"] == 0
    assert loser["three_dart_average"] == 60.0
    assert loser["checkout_percentage"] is None

    assert body["game_type"] == "x01"
    assert len(body["legs"]) == 1
    leg = body["legs"][0]
    assert leg["leg_number"] == 1
    assert leg["status"] == "completed"
    assert leg["winner_player_id"] == setup["own"]["id"]
    assert leg["darts_thrown"][setup["own"]["id"]] == 9
    assert leg["darts_thrown"][setup["guest"]["id"]] == 6


def test_match_summary_works_live_mid_match(client, setup):
    match = client.post(
        "/api/v1/matches",
        json={"opponent_player_id": setup["guest"]["id"], "best_of_legs": 3},
        headers=setup["headers"],
    ).json()
    client.post(
        f"/api/v1/matches/{match['id']}/visits",
        json={"player_id": setup["own"]["id"], "darts": [T20] * 3},
        headers=setup["headers"],
    )
    body = client.get(
        f"/api/v1/matches/{match['id']}/summary", headers=setup["headers"]
    ).json()
    assert body["status"] == "in_progress"
    by_id = {p["player_id"]: p for p in body["players"]}
    assert by_id[setup["own"]["id"]]["points_scored"] == 180
    assert by_id[setup["guest"]["id"]]["darts_thrown"] == 0


def test_match_summary_unknown_match_is_404(client, setup):
    response = client.get(
        f"/api/v1/matches/{uuid.uuid4()}/summary", headers=setup["headers"]
    )
    assert response.status_code == 404


def test_stats_for_unknown_player_is_404(client, setup):
    response = client.get(
        f"/api/v1/players/{uuid.uuid4()}/stats", headers=setup["headers"]
    )
    assert response.status_code == 404


def test_stats_require_authentication(client, setup):
    response = client.get(f"/api/v1/players/{setup['own']['id']}/stats")
    assert response.status_code == 401
