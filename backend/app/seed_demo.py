"""Seed a demo account with a realistic match history.

    python -m app.seed_demo            # creates demo@dartmetrics.app if absent
    python -m app.seed_demo --reset    # wipes the demo account's matches first

Everything goes through the normal services, so the seeded matches
obey every rule and count toward statistics exactly like real play.
Each side's darts come from the bot throw simulator with a chosen
accuracy, so the numbers look like a club player's rather than a
scripted nine-darter. The RNG is seeded, so a reset reproduces the
same history.

Run it against any database by setting DATABASE_URL, e.g. the
production one to give visitors a ready-made account to explore.
"""

from __future__ import annotations

import argparse
import random
import sys
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.auth.models import User
from app.auth.service import register_user
from app.db import get_sessionmaker
from app.matches import service as matches
from app.matches.models import (
    DartThrow,
    GameType,
    Leg,
    LegPlayerState,
    LegStatus,
    Match,
    MatchStatus,
    Turn,
)
from app.players.models import BotDifficulty, Player
from app.players.service import create_player, list_bots
from app.scoring import bot
from app.scoring.domain import DartInput

DEMO_EMAIL = "demo@dartmetrics.app"
DEMO_PASSWORD = "demo-darts"
DEMO_NAME = "Sam"

# Throwing personas. The demo player sits between the medium and hard
# bots (~72 three-dart average); the guests are club-standard.
PERSONAS: dict[str, bot.Accuracy] = {
    DEMO_NAME: bot.Accuracy(0.22, 0.30, 0.62, 0.20, 0.34, 0.72, 0.01, 0.40),
    "Jordan": bot.Accuracy(0.21, 0.28, 0.60, 0.18, 0.33, 0.70, 0.01, 0.42),
    "Riley": bot.Accuracy(0.12, 0.16, 0.48, 0.09, 0.22, 0.58, 0.04, 0.50),
}

# (opponent, game, best_of, days_ago). Opponent is a guest name or a bot
# difficulty. Oldest first so created_at ordering matches the story.
SCHEDULE: list[tuple[str, GameType, int, float]] = [
    ("Riley", GameType.X01, 3, 41),
    (BotDifficulty.EASY.value, GameType.X01, 3, 38.5),
    ("Jordan", GameType.X01, 5, 35),
    ("Riley", GameType.CRICKET, 3, 31),
    (BotDifficulty.MEDIUM.value, GameType.X01, 3, 27.2),
    ("Jordan", GameType.HALVE_IT, 1, 24),
    ("Jordan", GameType.X01, 5, 20),
    (BotDifficulty.HARD.value, GameType.X01, 3, 16.5),
    ("Riley", GameType.X01, 3, 13),
    (BotDifficulty.MEDIUM.value, GameType.CRICKET, 3, 9),
    ("Jordan", GameType.X01, 3, 6.3),
    (BotDifficulty.HARD.value, GameType.X01, 5, 3),
    ("Riley", GameType.HALVE_IT, 1, 1.2),
]


def _persona_darts(
    match: Match, state: LegPlayerState, accuracy: bot.Accuracy, rng: random.Random
) -> list[DartInput]:
    if match.game_type is GameType.CRICKET:
        return bot.cricket_visit(matches.marks_from_game_state(state.game_state), accuracy, rng)
    if match.game_type is GameType.HALVE_IT:
        _, round_number = matches.halve_it_state(state.game_state)
        return bot.halve_it_visit(round_number, accuracy, rng)
    return bot.x01_visit(state.remaining_score, accuracy, rng)


def _play_out(
    session: Session,
    user: User,
    match: Match,
    personas: dict[uuid.UUID, bot.Accuracy],
    rng: random.Random,
    stop_after_visits: int | None = None,
) -> None:
    """Alternate visits until the match completes (or a visit cap)."""
    visits = 0
    while match.status is MatchStatus.IN_PROGRESS:
        if stop_after_visits is not None and visits >= stop_after_visits:
            return
        state = matches.build_match_state(session, match)
        active = next(p for p in state["players"] if p["is_active_turn"])
        if active["bot_difficulty"]:
            _, match, _ = matches.record_bot_visit(session, user, match.id, rng)
        else:
            leg = next(l for l in match.legs if l.status is LegStatus.IN_PROGRESS)
            lps = session.scalar(
                select(LegPlayerState).where(
                    LegPlayerState.leg_id == leg.id,
                    LegPlayerState.player_id == active["player_id"],
                )
            )
            darts = _persona_darts(match, lps, personas[active["player_id"]], rng)
            _, match = matches.record_match_visit(session, user, match.id, active["player_id"], darts)
        session.flush()
        visits += 1


def _backdate(session: Session, match: Match, days_ago: float) -> None:
    """Shift the whole match into the past so history reads naturally."""
    start = datetime.now(timezone.utc) - timedelta(days=days_ago)
    offset = start - match.created_at
    match.created_at = start
    match.started_at = start
    if match.completed_at:
        match.completed_at = match.completed_at + offset
    for leg in match.legs:
        if leg.started_at:
            leg.started_at += offset
        if leg.completed_at:
            leg.completed_at += offset
        for turn in leg.turns:
            turn.created_at += offset
            for dart in turn.dart_throws:
                dart.created_at += offset


def _reset(session: Session, user: User) -> int:
    match_ids = list(session.scalars(select(Match.id).where(Match.created_by_user_id == user.id)))
    if not match_ids:
        return 0
    leg_ids = list(session.scalars(select(Leg.id).where(Leg.match_id.in_(match_ids))))
    turn_ids = list(session.scalars(select(Turn.id).where(Turn.leg_id.in_(leg_ids))))
    if turn_ids:
        session.execute(delete(DartThrow).where(DartThrow.turn_id.in_(turn_ids)))
        session.execute(delete(Turn).where(Turn.id.in_(turn_ids)))
    if leg_ids:
        session.execute(delete(LegPlayerState).where(LegPlayerState.leg_id.in_(leg_ids)))
        session.execute(delete(Leg).where(Leg.id.in_(leg_ids)))
    session.execute(delete(Match).where(Match.id.in_(match_ids)))
    return len(match_ids)


def seed(session: Session, reset: bool, seed_value: int) -> None:
    rng = random.Random(seed_value)

    user = session.scalar(select(User).where(func.lower(User.email) == DEMO_EMAIL))
    if user is None:
        user = register_user(session, DEMO_EMAIL, DEMO_PASSWORD, DEMO_NAME)
        session.flush()
        print(f"created {DEMO_EMAIL}")
    elif reset:
        print(f"reset: removed {_reset(session, user)} matches")
    else:
        print(f"{DEMO_EMAIL} already exists; use --reset to rebuild its history")
        return

    me = session.scalar(select(Player).where(Player.user_id == user.id))
    if me is None:
        me = create_player(session, user, DEMO_NAME, None, is_guest=False)
    guests: dict[str, Player] = {}
    for name in ("Jordan", "Riley"):
        guest = session.scalar(
            select(Player).where(Player.display_name == name, Player.user_id.is_(None), Player.bot_difficulty.is_(None))
        )
        guests[name] = guest or create_player(session, user, name, None, is_guest=True)
    bots = {b.bot_difficulty: b for b in list_bots(session)}
    session.flush()

    personas = {me.id: PERSONAS[DEMO_NAME], **{p.id: PERSONAS[n] for n, p in guests.items()}}

    for i, (opponent, game, best_of, days_ago) in enumerate(SCHEDULE):
        opp = bots[opponent] if opponent in bots else guests[opponent]
        starter = me.id if i % 2 == 0 else opp.id
        match = matches.create_match(session, user, opp.id, best_of, starter, game)
        session.flush()
        _play_out(session, user, match, personas, rng)
        _backdate(session, match, days_ago)
        session.flush()
        winner = "Sam" if match.winner_player_id == me.id else opp.display_name
        print(f"  {game.value:8s} best of {best_of} vs {opp.display_name:11s} -> {winner}")

    # One live match to resume: Sam has just thrown a 180 to sit on 321
    # with the bot to reply. Only the first visit is played so the
    # screenshot/tour can throw the rest.
    live = matches.create_match(session, user, bots[BotDifficulty.MEDIUM.value].id, 3, me.id, GameType.X01)
    session.flush()
    t20 = DartInput(20, bot.Multiplier.TRIPLE)
    matches.record_match_visit(session, user, live.id, me.id, [t20, t20, t20])
    _, live, _ = matches.record_bot_visit(session, user, live.id, rng)
    _backdate(session, live, 0.01)
    print(f"  x01      best of 3 vs Medium Bot  -> in progress (Sam to throw)")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--reset", action="store_true", help="delete the demo account's matches first")
    parser.add_argument("--seed", type=int, default=2026, help="RNG seed (default 2026)")
    args = parser.parse_args(argv)

    with get_sessionmaker()() as session:
        seed(session, args.reset, args.seed)
        session.commit()
    print(f"\nSign in as {DEMO_EMAIL} / {DEMO_PASSWORD}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
