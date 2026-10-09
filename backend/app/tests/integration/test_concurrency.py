"""Two sessions on the same leg at the same time.

The README advertises a transactional turn service with row locking.
These tests prove it with real concurrency: one session takes the lock
by recording a visit and holds it (no commit); a second session, on
its own connection and thread, tries to change the same leg. It must
wait for the lock, then act on the committed state rather than on
what it read earlier.

The rows are committed for real (two connections cannot share the
suite's rollback-wrapped transaction) and deleted afterwards.
"""

import threading
import uuid

import pytest
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.auth.models import User
from app.common.errors import LegNotActive, MatchNotActive, NotPlayersTurn
from app.matches import service
from app.matches.models import (
    DartThrow,
    Leg,
    LegPlayerState,
    LegStatus,
    Match,
    MatchStatus,
    Turn,
)
from app.players.models import Player
from app.scoring.domain import DartInput, Multiplier

T20 = DartInput(20, Multiplier.TRIPLE)
D20 = DartInput(20, Multiplier.DOUBLE)
LOCK_WAIT = 0.5  # seconds a blocked request must still be waiting


@pytest.fixture
def committed(engine):
    """A committed in-progress match: a human starter against a bot,
    best of 1. Yields ids; removes every row it created afterwards."""
    ids: dict[str, uuid.UUID] = {}
    with Session(engine) as session:
        user = User(
            email=f"lock-{uuid.uuid4().hex[:8]}@example.com",
            password_hash="x",
            display_name="Locker",
        )
        human = Player(display_name="Locker", user_id=None)
        session.add_all([user, human])
        session.flush()
        human.user_id = user.id
        # The shared bots come from the migration (one per difficulty).
        bot = session.scalar(select(Player).where(Player.bot_difficulty == "pro"))
        assert bot is not None, "run alembic upgrade head"
        match = Match(
            created_by_user_id=user.id,
            player1_id=human.id,
            player2_id=bot.id,
            best_of_legs=1,
            status=MatchStatus.IN_PROGRESS,
        )
        session.add(match)
        session.flush()
        leg = Leg(
            match_id=match.id,
            leg_number=1,
            starting_player_id=human.id,
            status=LegStatus.IN_PROGRESS,
        )
        session.add(leg)
        session.flush()
        session.add_all(
            [
                LegPlayerState(leg_id=leg.id, player_id=human.id),
                LegPlayerState(leg_id=leg.id, player_id=bot.id),
            ]
        )
        session.commit()
        ids = {"user": user.id, "human": human.id, "bot": bot.id, "match": match.id, "leg": leg.id}

    try:
        yield ids
    finally:
        with Session(engine) as session:
            turn_ids = select(Turn.id).where(Turn.leg_id == ids["leg"])
            session.execute(delete(DartThrow).where(DartThrow.turn_id.in_(turn_ids)))
            session.execute(delete(Turn).where(Turn.leg_id == ids["leg"]))
            session.execute(delete(LegPlayerState).where(LegPlayerState.leg_id == ids["leg"]))
            session.execute(delete(Leg).where(Leg.match_id == ids["match"]))
            session.execute(delete(Match).where(Match.id == ids["match"]))
            session.execute(delete(Player).where(Player.id == ids["human"]))
            session.execute(delete(User).where(User.id == ids["user"]))
            session.commit()


class Later:
    """Run a session-bound action on its own thread and connection,
    reporting its result or exception once it gets through."""

    def __init__(self, engine, action):
        self.result = None
        self.error: Exception | None = None

        def run():
            with Session(engine) as session:
                try:
                    self.result = action(session)
                    session.commit()
                except Exception as exc:  # noqa: BLE001 - reported to the test
                    self.error = exc
                    session.rollback()

        self.thread = threading.Thread(target=run, daemon=True)
        self.thread.start()

    def still_waiting(self) -> bool:
        self.thread.join(LOCK_WAIT)
        return self.thread.is_alive()

    def finish(self):
        self.thread.join(10)
        assert not self.thread.is_alive(), "second session never got through the lock"
        return self.result, self.error


def _lock_with_a_visit(engine, ids, darts=(T20, T20, T20)) -> Session:
    """First session: record a visit and keep the transaction open, so
    the FOR UPDATE lock on the leg's state rows stays held."""
    session = Session(engine)
    service.record_turn(session, ids["leg"], ids["human"], list(darts))
    return session


def test_second_visit_waits_for_the_lock_then_gets_the_turn_order_right(engine, committed):
    holder = _lock_with_a_visit(engine, committed)
    try:
        second = Later(
            engine,
            lambda s: service.record_turn(s, committed["leg"], committed["human"], [T20, T20, T20]),
        )
        assert second.still_waiting()
        holder.commit()
    finally:
        holder.close()

    _, error = second.finish()
    assert isinstance(error, NotPlayersTurn)


def test_undo_waits_for_an_in_flight_visit_and_removes_that_one(engine, committed):
    """Undo tapped right after a mis-tapped third dart used to race the
    visit: without the lock it removed the previous visit and left a
    gap in the turn numbers, after which every visit was a 409."""
    holder = _lock_with_a_visit(engine, committed)
    try:
        with Session(engine) as s:
            user = s.get(User, committed["user"])
            s.expunge(user)
        undo = Later(engine, lambda s: service.undo_latest_visit(s, user, committed["match"]))
        assert undo.still_waiting()
        holder.commit()
    finally:
        holder.close()

    _, error = undo.finish()
    assert error is None

    with Session(engine) as s:
        assert s.scalar(select(Turn).where(Turn.leg_id == committed["leg"])) is None
        state = s.scalar(
            select(LegPlayerState).where(
                LegPlayerState.leg_id == committed["leg"],
                LegPlayerState.player_id == committed["human"],
            )
        )
        assert (state.turns_taken, state.darts_thrown, state.remaining_score) == (0, 0, 501)


def test_bot_visit_waits_for_the_lock_and_sees_the_committed_turn_count(engine, committed):
    """The bot path read the state rows before record_turn locked them,
    so it decided whose turn it was from stale rows: here it would have
    answered NOT_BOT_TURN at once instead of waiting and then throwing."""
    holder = _lock_with_a_visit(engine, committed)
    try:
        with Session(engine) as s:
            user = s.get(User, committed["user"])
            s.expunge(user)
        def bot_throws(s):
            turn, _, darts = service.record_bot_visit(s, user, committed["match"])
            return turn.player_id, turn.turn_number, len(darts)

        bot = Later(engine, bot_throws)
        assert bot.still_waiting()
        holder.commit()
    finally:
        holder.close()

    result, error = bot.finish()
    assert error is None
    player_id, turn_number, dart_count = result
    assert player_id == committed["bot"]
    assert turn_number == 2
    assert 1 <= dart_count <= 3


def test_visit_on_a_leg_completed_by_another_session_is_rejected(engine, committed):
    """Status was checked before the lock, so a visit from a second
    device could land on a leg the first had just finished."""
    with Session(engine) as s:
        state = s.scalar(
            select(LegPlayerState).where(
                LegPlayerState.leg_id == committed["leg"],
                LegPlayerState.player_id == committed["human"],
            )
        )
        state.remaining_score = 40
        s.commit()

    holder = _lock_with_a_visit(engine, committed, darts=(D20,))  # wins leg and match
    try:
        late = Later(
            engine,
            lambda s: service.record_turn(s, committed["leg"], committed["bot"], [T20]),
        )
        assert late.still_waiting()
        holder.commit()
    finally:
        holder.close()

    _, error = late.finish()
    assert isinstance(error, (MatchNotActive, LegNotActive))
    with Session(engine) as s:
        assert s.scalar(select(Turn.turn_number).where(Turn.leg_id == committed["leg"]).order_by(Turn.turn_number.desc())) == 1
