"""Integration tests: a complete 501 leg played through the turn
service against real PostgreSQL (Phase 0 deliverable, spec section 20
item 10).
"""

import pytest
from sqlalchemy import select

from app.common.errors import DomainError, NotPlayersTurn
from app.matches.models import DartThrow, LegStatus, MatchStatus, Turn
from app.matches.service import record_turn
from app.scoring.domain import double, single, triple
from app.scoring.engine import apply_dart


def test_full_leg_from_501_to_checkout(db_session, match_setup):
    """Play a scripted nine-dart leg for player 1 and verify all
    persisted state: turns, darts, scores, winners, lifecycle."""
    s, ms = db_session, match_setup

    # Player 1 throws a nine-darter: 180, 180, then 141 out (T20 T19 D12).
    record_turn(s, ms.leg.id, ms.player1.id, [triple(20)] * 3)      # 321
    record_turn(s, ms.leg.id, ms.player2.id, [single(20)] * 3)      # 441
    record_turn(s, ms.leg.id, ms.player1.id, [triple(20)] * 3)      # 141
    record_turn(s, ms.leg.id, ms.player2.id, [single(19)] * 3)      # 384
    final = record_turn(
        s, ms.leg.id, ms.player1.id, [triple(20), triple(19), double(12)]
    )

    assert final.is_checkout and not final.is_bust
    assert final.turn_end_score == 0
    assert final.points_scored == 141

    # Leg and match lifecycle (best-of-1: winning the leg wins the match)
    assert ms.leg.status is LegStatus.COMPLETED
    assert ms.leg.winner_player_id == ms.player1.id
    assert ms.leg.completed_at is not None
    assert ms.match.status is MatchStatus.COMPLETED
    assert ms.match.winner_player_id == ms.player1.id

    # Per-player state
    assert ms.state1.remaining_score == 0
    assert ms.state1.has_won is True
    assert ms.state1.darts_thrown == 9
    assert ms.state1.turns_taken == 3
    assert ms.state2.remaining_score == 501 - 60 - 57
    assert ms.state2.has_won is False
    assert ms.state2.darts_thrown == 6

    # Raw event history: 5 turns, 15 darts, sequential turn numbers
    turns = list(
        s.scalars(select(Turn).where(Turn.leg_id == ms.leg.id).order_by(Turn.turn_number))
    )
    assert [t.turn_number for t in turns] == [1, 2, 3, 4, 5]
    darts = list(s.scalars(select(DartThrow).where(DartThrow.turn_id.in_(t.id for t in turns))))
    assert len(darts) == 15
    winning = [d for d in darts if d.is_winning_dart]
    assert len(winning) == 1
    assert winning[0].segment == "12" and winning[0].is_double


def test_bust_persists_restored_score(db_session, match_setup):
    s, ms = db_session, match_setup

    # Bring player 1 down to 40 (461 scored over 3 turns: 180, 180, 101),
    # with filler turns from player 2 to keep alternation legal.
    record_turn(s, ms.leg.id, ms.player1.id, [triple(20)] * 3)               # 321
    record_turn(s, ms.leg.id, ms.player2.id, [single(20)] * 3)
    record_turn(s, ms.leg.id, ms.player1.id, [triple(20)] * 3)               # 141
    record_turn(s, ms.leg.id, ms.player2.id, [single(20)] * 3)
    record_turn(s, ms.leg.id, ms.player1.id, [triple(20), single(20), single(1)])  # 60 left
    record_turn(s, ms.leg.id, ms.player2.id, [single(20)] * 3)
    # From 60, three single 20s reach exactly 0 on a non-double: bust on dart 3.
    record_turn(s, ms.leg.id, ms.player1.id, [single(20)] * 3)

    assert ms.state1.remaining_score == 60  # bust restored the pre-turn score

    bust_turn = s.scalars(
        select(Turn).where(Turn.leg_id == ms.leg.id).order_by(Turn.turn_number.desc())
    ).first()
    assert bust_turn.is_bust is True
    assert bust_turn.points_scored == 0
    assert bust_turn.turn_end_score == bust_turn.turn_start_score == 60
    # Bust darts remain recorded for audit even though they score nothing
    assert len(bust_turn.dart_throws) == 3


def test_invalid_command_persists_nothing(db_session, match_setup):
    s, ms = db_session, match_setup

    with pytest.raises(NotPlayersTurn):
        record_turn(s, ms.leg.id, ms.player2.id, [triple(20)] * 3)

    turns = list(s.scalars(select(Turn).where(Turn.leg_id == ms.leg.id)))
    assert turns == []
    assert ms.state2.turns_taken == 0
    assert ms.state2.remaining_score == 501


def test_database_rejects_corrupt_turn_row(db_session, match_setup):
    """Belt-and-braces: even bypassing the service, PostgreSQL's check
    constraints refuse a self-contradictory turn."""
    from sqlalchemy.exc import IntegrityError

    s, ms = db_session, match_setup
    s.add(
        Turn(
            leg_id=ms.leg.id,
            player_id=ms.player1.id,
            turn_number=1,
            turn_start_score=501,
            turn_end_score=441,
            points_scored=100,  # contradicts 501-441
        )
    )
    with pytest.raises(IntegrityError):
        s.flush()
