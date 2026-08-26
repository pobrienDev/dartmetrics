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

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.models import User
from app.common.errors import (
    InvalidMatchSetup,
    InvalidTurn,
    LegNotActive,
    MatchAccessDenied,
    MatchNotActive,
    MatchNotFound,
    MissingPlayerProfile,
    NotPlayersTurn,
    PlayerNotFound,
    PlayerNotInMatch,
    UndoNotAvailable,
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
from app.players.models import Player
from app.scoring.domain import DartInput
from app.scoring.engine import apply_dart

MAX_DARTS_PER_TURN = 3
STARTING_SCORE = 501


def create_match(
    session: Session,
    user: User,
    opponent_player_id: uuid.UUID,
    best_of_legs: int,
    starting_player_id: uuid.UUID | None,
) -> Match:
    """Create a match between the user's player and an opponent, and
    immediately start leg 1 at 501-501 (dev plan core workflow step 5)."""
    own_player = session.scalar(select(Player).where(Player.user_id == user.id))
    if own_player is None:
        raise MissingPlayerProfile(
            "Create your player profile before starting a match."
        )

    opponent = session.get(Player, opponent_player_id)
    if opponent is None:
        raise PlayerNotFound(f"Player {opponent_player_id} does not exist.")
    if opponent.id == own_player.id:
        raise InvalidMatchSetup("You cannot play a match against yourself.")

    starter_id = starting_player_id or own_player.id
    if starter_id not in (own_player.id, opponent.id):
        raise InvalidMatchSetup("starting_player_id must be one of the participants.")

    now = datetime.now(timezone.utc)
    match = Match(
        created_by_user_id=user.id,
        player1_id=own_player.id,
        player2_id=opponent.id,
        best_of_legs=best_of_legs,
        status=MatchStatus.IN_PROGRESS,
        started_at=now,
        # Stamped app-side: PostgreSQL's now() is the TRANSACTION start
        # time, so rows created in one transaction would tie and make
        # newest-first ordering arbitrary.
        created_at=now,
    )
    session.add(match)
    session.flush()

    _start_leg(session, match, leg_number=1, starting_player_id=starter_id, now=now)
    session.flush()
    return match


def _start_leg(
    session: Session,
    match: Match,
    leg_number: int,
    starting_player_id: uuid.UUID,
    now: datetime,
) -> Leg:
    leg = Leg(
        match_id=match.id,
        leg_number=leg_number,
        starting_player_id=starting_player_id,
        status=LegStatus.IN_PROGRESS,
        started_at=now,
    )
    session.add(leg)
    session.flush()
    session.add_all(
        [
            LegPlayerState(leg_id=leg.id, player_id=match.player1_id),
            LegPlayerState(leg_id=leg.id, player_id=match.player2_id),
        ]
    )
    return leg


def get_match(session: Session, match_id: uuid.UUID) -> Match:
    match = session.get(Match, match_id)
    if match is None:
        raise MatchNotFound(f"Match {match_id} does not exist.")
    return match


def list_matches(
    session: Session,
    user: User,
    status: MatchStatus | None,
    limit: int,
    offset: int,
) -> tuple[list[dict], int]:
    """The user's matches (created or playing in), newest first."""
    own_player_ids = select(Player.id).where(Player.user_id == user.id)
    visibility = (
        (Match.created_by_user_id == user.id)
        | Match.player1_id.in_(own_player_ids)
        | Match.player2_id.in_(own_player_ids)
    )

    conditions = [visibility]
    if status is not None:
        conditions.append(Match.status == status)

    total = session.scalar(select(func.count(Match.id)).where(*conditions))
    matches = list(
        session.scalars(
            select(Match)
            .where(*conditions)
            .order_by(Match.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
    )

    items = []
    for match in matches:
        players = []
        for player_id in (match.player1_id, match.player2_id):
            player = session.get(Player, player_id)
            players.append(
                {
                    "player_id": player_id,
                    "display_name": player.display_name,
                    "legs_won": sum(
                        1 for leg in match.legs if leg.winner_player_id == player_id
                    ),
                }
            )
        items.append(
            {
                "id": match.id,
                "status": match.status,
                "best_of_legs": match.best_of_legs,
                "winner_player_id": match.winner_player_id,
                "created_at": match.created_at,
                "started_at": match.started_at,
                "completed_at": match.completed_at,
                "players": players,
            }
        )
    return items, total


def _ensure_can_score(session: Session, user: User, match: Match) -> None:
    """Only the match creator or a participant may record visits
    (dev plan authorization matrix). Guests are scored by the creator."""
    if user.id == match.created_by_user_id:
        return
    own_player = session.scalar(
        select(Player).where(
            Player.user_id == user.id,
            Player.id.in_([match.player1_id, match.player2_id]),
        )
    )
    if own_player is None:
        raise MatchAccessDenied("You are not a participant in this match.")


def record_match_visit(
    session: Session,
    user: User,
    match_id: uuid.UUID,
    player_id: uuid.UUID,
    darts: list[DartInput],
) -> tuple[Turn, Match]:
    """Record one visit against the match's active leg and, when the
    visit wins a leg mid-match, start the next leg with the alternated
    starter (Phase 0 spec 17.1)."""
    match = get_match(session, match_id)
    _ensure_can_score(session, user, match)

    if match.status is not MatchStatus.IN_PROGRESS:
        raise MatchNotActive(f"Match is {match.status}; scoring is not allowed.")

    leg = next(
        (leg for leg in match.legs if leg.status is LegStatus.IN_PROGRESS), None
    )
    if leg is None:
        raise LegNotActive("The match has no active leg.")

    turn = record_turn(session, leg.id, player_id, darts)

    if leg.status is LegStatus.COMPLETED and match.status is MatchStatus.IN_PROGRESS:
        other_starter = (
            match.player2_id
            if leg.starting_player_id == match.player1_id
            else match.player1_id
        )
        _start_leg(
            session,
            match,
            leg_number=leg.leg_number + 1,
            starting_player_id=other_starter,
            now=datetime.now(timezone.utc),
        )
        # The legs collection was loaded before the new leg existed
        session.expire(match, ["legs"])

    session.flush()
    return turn, match


def abandon_match(session: Session, user: User, match_id: uuid.UUID) -> Match:
    """Cancel an in-progress match. No winner is recorded, and
    cancelled matches are excluded from win statistics. The active
    leg keeps its in-progress rows untouched for audit; the cancelled
    match status is what blocks any further scoring."""
    match = get_match(session, match_id)
    _ensure_can_score(session, user, match)

    if match.status is not MatchStatus.IN_PROGRESS:
        raise MatchNotActive(f"Match is {match.status}; only an in-progress match can be abandoned.")

    match.status = MatchStatus.CANCELLED
    match.completed_at = datetime.now(timezone.utc)
    session.flush()
    return match


def undo_latest_visit(session: Session, user: User, match_id: uuid.UUID) -> Match:
    """Remove the most recent visit in the active leg and restore the
    scoreboard (spec 13.4: latest active-leg visit only — completed
    legs are immutable in the MVP)."""
    match = get_match(session, match_id)
    _ensure_can_score(session, user, match)

    if match.status is not MatchStatus.IN_PROGRESS:
        raise MatchNotActive(f"Match is {match.status}; undo is not allowed.")

    leg = next(
        (leg for leg in match.legs if leg.status is LegStatus.IN_PROGRESS), None
    )
    if leg is None:
        raise LegNotActive("The match has no active leg.")

    latest = session.scalars(
        select(Turn)
        .where(Turn.leg_id == leg.id)
        .order_by(Turn.turn_number.desc())
        .limit(1)
    ).first()
    if latest is None:
        raise UndoNotAvailable(
            "No visit exists in the active leg to undo. Completed legs "
            "cannot be modified."
        )

    state = session.scalar(
        select(LegPlayerState).where(
            LegPlayerState.leg_id == leg.id,
            LegPlayerState.player_id == latest.player_id,
        )
    )
    state.remaining_score = latest.turn_start_score
    state.darts_thrown -= len(latest.dart_throws)
    state.turns_taken -= 1

    for dart in latest.dart_throws:
        session.delete(dart)
    session.delete(latest)

    session.flush()
    return match


def build_match_state(session: Session, match: Match) -> dict:
    """Assemble the authoritative scoreboard for MatchStateResponse."""
    current_leg = next(
        (leg for leg in match.legs if leg.status is LegStatus.IN_PROGRESS), None
    )

    states: dict[uuid.UUID, LegPlayerState] = {}
    active_player_id = None
    if current_leg is not None:
        states = {
            s.player_id: s
            for s in session.scalars(
                select(LegPlayerState).where(LegPlayerState.leg_id == current_leg.id)
            )
        }
        total_turns = sum(s.turns_taken for s in states.values())
        active_player_id = _expected_player_id(current_leg, total_turns)

    players = []
    for player_id in (match.player1_id, match.player2_id):
        player = session.get(Player, player_id)
        state = states.get(player_id)
        players.append(
            {
                "player_id": player_id,
                "display_name": player.display_name,
                "legs_won": sum(
                    1 for leg in match.legs if leg.winner_player_id == player_id
                ),
                "remaining_score": state.remaining_score if state else None,
                "is_active_turn": player_id == active_player_id,
            }
        )

    return {
        "id": match.id,
        "status": match.status,
        "best_of_legs": match.best_of_legs,
        "legs_required_to_win": match.legs_required_to_win,
        "winner_player_id": match.winner_player_id,
        "players": players,
        "current_leg": (
            {
                "id": current_leg.id,
                "leg_number": current_leg.leg_number,
                "status": current_leg.status,
                "starting_player_id": current_leg.starting_player_id,
                "winner_player_id": current_leg.winner_player_id,
            }
            if current_leg
            else None
        ),
    }


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
