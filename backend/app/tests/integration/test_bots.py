"""Integration tests for bot opponents."""

import random
import uuid

import pytest
from sqlalchemy import select

from app.matches import service
from app.matches.models import Match
from app.players.models import Player


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
    headers = signup(client, "pat@example.com", "Patrick")
    own = client.post(
        "/api/v1/players", json={"display_name": "Patrick"}, headers=headers
    ).json()
    bots = client.get("/api/v1/players/bots", headers=headers).json()
    return {"headers": headers, "own": own, "bots": bots}


def test_bots_listed_easiest_to_hardest_and_idempotent(client, setup):
    difficulties = [b["bot_difficulty"] for b in setup["bots"]]
    assert difficulties == ["noob", "easy", "medium", "hard", "pro"]
    assert all(b["user_id"] is None for b in setup["bots"])

    again = client.get("/api/v1/players/bots", headers=setup["headers"]).json()
    assert [b["id"] for b in again] == [b["id"] for b in setup["bots"]]


def test_bots_are_not_in_the_human_player_list(client, setup):
    humans = client.get("/api/v1/players", headers=setup["headers"]).json()
    assert all(p["bot_difficulty"] is None for p in humans)


def test_bot_visit_requires_the_bots_turn(client, setup):
    pro = next(b for b in setup["bots"] if b["bot_difficulty"] == "pro")
    match = client.post(
        "/api/v1/matches",
        json={"opponent_player_id": pro["id"], "best_of_legs": 1},
        headers=setup["headers"],
    ).json()
    response = client.post(f"/api/v1/matches/{match['id']}/bot-visit", headers=setup["headers"])
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "NOT_BOT_TURN"


def test_bot_visit_records_darts_and_hands_the_turn_back(client, setup):
    pro = next(b for b in setup["bots"] if b["bot_difficulty"] == "pro")
    match = client.post(
        "/api/v1/matches",
        json={
            "opponent_player_id": pro["id"],
            "best_of_legs": 1,
            "starting_player_id": pro["id"],
        },
        headers=setup["headers"],
    ).json()
    state = match["players"]
    assert next(p for p in state if p["is_active_turn"])["bot_difficulty"] == "pro"

    response = client.post(f"/api/v1/matches/{match['id']}/bot-visit", headers=setup["headers"])
    assert response.status_code == 201
    body = response.json()
    assert body["turn"]["player_id"] == pro["id"]
    assert 1 <= len(body["darts"]) <= 3
    assert body["turn"]["points_scored"] == sum(
        0 if d["multiplier"] == "miss" else d["segment"] * {"single": 1, "double": 2, "triple": 3}[d["multiplier"]]
        for d in body["darts"]
    ) or body["turn"]["is_bust"]
    bot_state = next(p for p in body["state"]["players"] if p["player_id"] == pro["id"])
    assert bot_state["remaining_score"] == body["turn"]["turn_end_score"]
    assert not bot_state["is_active_turn"]


def test_bot_visits_work_in_every_game_mode(client, setup):
    medium = next(b for b in setup["bots"] if b["bot_difficulty"] == "medium")
    for game_type in ("x01", "cricket", "halve_it"):
        match = client.post(
            "/api/v1/matches",
            json={
                "opponent_player_id": medium["id"],
                "best_of_legs": 1,
                "game_type": game_type,
                "starting_player_id": medium["id"],
            },
            headers=setup["headers"],
        ).json()
        response = client.post(f"/api/v1/matches/{match['id']}/bot-visit", headers=setup["headers"])
        assert response.status_code == 201, (game_type, response.json())
        assert response.json()["turn"]["player_id"] == medium["id"]


def test_undo_against_a_bot_removes_the_bots_reply_too(client, setup):
    hard = next(b for b in setup["bots"] if b["bot_difficulty"] == "hard")
    match = client.post(
        "/api/v1/matches",
        json={"opponent_player_id": hard["id"], "best_of_legs": 1},
        headers=setup["headers"],
    ).json()
    url = f"/api/v1/matches/{match['id']}"

    client.post(
        f"{url}/visits",
        json={
            "player_id": setup["own"]["id"],
            "darts": [{"segment": 20, "multiplier": "triple"}] * 3,
        },
        headers=setup["headers"],
    )
    assert client.post(f"{url}/bot-visit", headers=setup["headers"]).status_code == 201

    undone = client.delete(f"{url}/visits/latest", headers=setup["headers"]).json()
    for player in undone["players"]:
        assert player["remaining_score"] == 501
    active = next(p for p in undone["players"] if p["is_active_turn"])
    assert active["player_id"] == setup["own"]["id"]


def test_undo_before_the_bot_replies_removes_only_the_human_visit(client, setup):
    easy = next(b for b in setup["bots"] if b["bot_difficulty"] == "easy")
    match = client.post(
        "/api/v1/matches",
        json={"opponent_player_id": easy["id"], "best_of_legs": 1},
        headers=setup["headers"],
    ).json()
    url = f"/api/v1/matches/{match['id']}"
    client.post(
        f"{url}/visits",
        json={
            "player_id": setup["own"]["id"],
            "darts": [{"segment": 20, "multiplier": "single"}] * 3,
        },
        headers=setup["headers"],
    )
    undone = client.delete(f"{url}/visits/latest", headers=setup["headers"]).json()
    active = next(p for p in undone["players"] if p["is_active_turn"])
    assert active["player_id"] == setup["own"]["id"]


def test_full_leg_against_pro_bot_completes(client, setup, db_session):
    """Both sides driven by the bot engine (the human's darts are
    generated the same way and posted as a normal visit) — the leg
    must reach a winner with every rule enforced along the way."""
    pro = next(b for b in setup["bots"] if b["bot_difficulty"] == "pro")
    match = client.post(
        "/api/v1/matches",
        json={"opponent_player_id": pro["id"], "best_of_legs": 1},
        headers=setup["headers"],
    ).json()
    url = f"/api/v1/matches/{match['id']}"
    rng = random.Random(99)
    from app.scoring import bot

    state = match
    for _ in range(200):
        if state["status"] != "in_progress":
            break
        active = next(p for p in state["players"] if p["is_active_turn"])
        if active["bot_difficulty"]:
            state = client.post(f"{url}/bot-visit", headers=setup["headers"]).json()["state"]
        else:
            darts = bot.x01_visit(active["remaining_score"], bot.ACCURACY["pro"], rng)
            response = client.post(
                f"{url}/visits",
                json={
                    "player_id": active["player_id"],
                    "darts": [
                        {"segment": d.segment, "multiplier": d.multiplier.name.lower()}
                        for d in darts
                    ],
                },
                headers=setup["headers"],
            )
            assert response.status_code == 201, response.json()
            state = response.json()["state"]
    assert state["status"] == "completed"
    assert state["winner_player_id"] in (pro["id"], setup["own"]["id"])
