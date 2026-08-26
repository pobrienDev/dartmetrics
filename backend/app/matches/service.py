"""Turn service: applies darts through the scoring engine and persists
the results (Phase 0 spec, sections 17-18; spec item 9 of the
implementation order).

record_turn writes one complete visit inside the caller's transaction.
The caller commits; if anything raises, nothing is persisted, so a
saved turn can never disagree with the scoreboard.

Checkout-attempt inference (documented per spec section 16): a dart is
recorded as a checkout attempt when the player's remaining score
before that dart was finishable with a single double (an even number
from 2 to 40, or exactly 50). This errs toward counting genuine
attempts without requiring UI intent data; revisit when the scoring
UI can capture the player's actual target.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.common.errors import (
    InvalidTurn,
    LegNotActive,
    MatchNotActive,
    NotPlayersTurn,
    PlayerNotInMatch,
)
from app.matches.models import (
    DartThrow,
    Leg,
    LegPlayerState,
    LegStatus,
    Match,
    MatchStatus,
    Turn,
)
from app.scoring.domain import DartInput
from app.scoring.engine import apply_dart

MAX_DARTS_PER_TURN = 3


def _is_double_finishable(score: int) -> bool:
    return score == 50 or (2 <= score <= 40 and score % 2 == 0)


def _expected_player_id(leg: Leg, total_turns_taken: int) -> uuid.UUID:
    """Turns strictly alternate starting with the leg's starting player."""
    match = leg.match
    starter = leg.starting_player_id
    other = match.player2_id if starter == match.player1_id else match.player1_id
    return starter if total_turns_taken % 2 == 0 else other


def record_turn(
    session: Session,
    leg_id: uuid.UUID,
    player_id: uuid.UUID,
    darts: list[DartInput],
) -> Turn:
    """Record one complete visit (1-3 darts) for the given player.

    Returns the persisted Turn. Raises a DomainError subclass for any
    rule violation; in that case the session is left unflushed and the
    caller's rollback discards everything.
    """
    if not darts:
        raise InvalidTurn("A turn must contain at least one dart.")
    if len(darts) > MAX_DARTS_PER_TURN:
        raise InvalidTurn("A turn cannot contain more than three darts.")

    leg = session.get(Leg, leg_id)
    if leg is None:
        raise LegNotActive(f"Leg {leg_id} does not exist.")
    match = leg.match

    if match.status is not MatchStatus.IN_PROGRESS:
        raise MatchNotActive(f"Match is {match.status}; scoring is not allowed.")
    if leg.status is not LegStatus.IN_PROGRESS:
        raise LegNotActive(f"Leg {leg.leg_number} is {leg.status}; scoring is not allowed.")
    if player_id not in (match.player1_id, match.player2_id):
        raise PlayerNotInMatch(f"Player {player_id} is not in this match.")

    states = {
        s.player_id: s
        for s in session.scalars(
            select(LegPlayerState).where(LegPlayerState.leg_id == leg.id)
        )
    }
    state = states[player_id]
    total_turns = sum(s.turns_taken for s in states.values())
    expected = _expected_player_id(leg, total_turns)
    if player_id != expected:
        raise NotPlayersTurn(f"It is not player {player_id}'s turn.")

    turn_start = state.remaining_score
    remaining = turn_start
    results = []
    for index, dart in enumerate(darts):
        result = apply_dart(turn_start, remaining, dart)
        results.append(result)
        if result.turn_should_end and index < len(darts) - 1:
            raise InvalidTurn(
                "The turn ended (bust or checkout) before all submitted darts; "
                "no darts may follow the ending dart."
            )
        remaining = result.effective_remaining

    final = results[-1]
    if not final.turn_should_end and len(darts) < MAX_DARTS_PER_TURN:
        raise InvalidTurn(
            "A turn must contain three darts unless a bust or checkout ends it early."
        )

    now = datetime.now(timezone.utc)
    turn = Turn(
        leg_id=leg.id,
        player_id=player_id,
        turn_number=total_turns + 1,
        turn_start_score=turn_start,
        turn_end_score=final.effective_remaining,
        points_scored=0 if final.is_bust else turn_start - final.effective_remaining,
        is_bust=final.is_bust,
        is_checkout=final.is_checkout,
    )
    session.add(turn)
    session.flush()  # assign turn.id before darts reference it

    score_before = turn_start
    for index, (dart, result) in enumerate(zip(darts, results), start=1):
        session.add(
            DartThrow(
                turn_id=turn.id,
                dart_number=index,
                segment="MISS" if dart.segment is None else str(dart.segment),
                multiplier=dart.multiplier.value,
                score=result.dart_score,
                is_double=dart.is_double,
                is_checkout_attempt=_is_double_finishable(score_before),
                is_winning_dart=result.is_checkout,
            )
        )
        score_before = result.tentative_remaining if not result.is_bust else score_before

    state.remaining_score = final.effective_remaining
    state.darts_thrown += len(darts)
    state.turns_taken += 1

    if final.is_checkout:
        state.has_won = True
        leg.status = LegStatus.COMPLETED
        leg.winner_player_id = player_id
        leg.completed_at = now

        legs_won = sum(
            1
            for completed_leg in match.legs
            if completed_leg.winner_player_id == player_id
        )
        if legs_won >= match.legs_required_to_win:
            match.status = MatchStatus.COMPLETED
            match.winner_player_id = player_id
            match.completed_at = now

    session.flush()
    return turn
