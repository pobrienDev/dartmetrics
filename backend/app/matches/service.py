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

import random
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
    NotBotsTurn,
    NotPlayersTurn,
    PlayerNotFound,
    PlayerNotInMatch,
    UndoNotAvailable,
)
from dataclasses import dataclass, field

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
from app.scoring import bot
from app.scoring.cricket import apply_cricket_dart, initial_marks
from app.scoring.domain import DartInput, Multiplier
from app.scoring.engine import apply_dart
from app.scoring.halve_it import (
    DARTS_PER_ROUND,
    STARTING_SCORE as HALVE_IT_STARTING_SCORE,
    apply_halve_it_visit,
    round_for_number,
)

MAX_DARTS_PER_TURN = 3
STARTING_SCORE = 501


def create_match(
    session: Session,
    user: User,
    opponent_player_id: uuid.UUID,
    best_of_legs: int,
    starting_player_id: uuid.UUID | None,
    game_type: GameType = GameType.X01,
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
        game_type=game_type,
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
    if match.game_type is GameType.CRICKET:
        game_state = {str(t): 0 for t in initial_marks()}
    elif match.game_type is GameType.HALVE_IT:
        game_state = {"score": HALVE_IT_STARTING_SCORE, "round": 1}
    else:
        game_state = None
    session.add_all(
        [
            LegPlayerState(
                leg_id=leg.id, player_id=match.player1_id, game_state=game_state
            ),
            LegPlayerState(
                leg_id=leg.id, player_id=match.player2_id, game_state=game_state
            ),
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
                "game_type": match.game_type,
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


def _halve_it_leg_winner(
    states: dict[uuid.UUID, LegPlayerState],
    thrower_id: uuid.UUID,
    outcome: "_VisitOutcome",
) -> uuid.UUID | None:
    """The leg ends when the second player of a round finishes it, the
    completed round is at least 9, and the scores differ. Ties roll on
    into extra Red Bull rounds."""
    completed_round = outcome.new_game_state["round"] - 1
    my_score = outcome.new_game_state["score"]

    other_id, other_state = next(
        (pid, s) for pid, s in states.items() if pid != thrower_id
    )
    other_score, other_round = halve_it_state(other_state.game_state)

    i_finished_second = other_round == outcome.new_game_state["round"]
    if not i_finished_second or completed_round < 9 or my_score == other_score:
        return None
    return thrower_id if my_score > other_score else other_id


def ensure_match_access(session: Session, user: User, match: Match) -> None:
    """Only the match creator or a participant may read or act on a
    match (dev plan authorization matrix). Guests are scored by the
    creator. Applies to reads too: match state and summaries are
    private to the people in the match."""
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


def get_match_for_user(session: Session, user: User, match_id: uuid.UUID) -> Match:
    """Load a match the user is allowed to see (404 unknown, 403 other people's)."""
    match = get_match(session, match_id)
    ensure_match_access(session, user, match)
    return match


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
    ensure_match_access(session, user, match)

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


def record_bot_visit(
    session: Session,
    user: User,
    match_id: uuid.UUID,
    rng: random.Random | None = None,
) -> tuple[Turn, Match, list[DartInput]]:
    """Generate and record a visit for the bot whose turn it is.

    The darts come from the pure bot engine and are then recorded
    through record_match_visit, so a bot visit obeys every rule and
    counts toward statistics exactly like a human's. The client drives
    the timing (it calls this when the scoreboard shows a bot as
    active), which keeps the API stateless and lets the UI pace the
    bot's throw.
    """
    match = get_match(session, match_id)
    ensure_match_access(session, user, match)
    if match.status is not MatchStatus.IN_PROGRESS:
        raise MatchNotActive(f"Match is {match.status}; scoring is not allowed.")

    leg = next(
        (leg for leg in match.legs if leg.status is LegStatus.IN_PROGRESS), None
    )
    if leg is None:
        raise LegNotActive("The match has no active leg.")

    states = {
        s.player_id: s
        for s in session.scalars(
            select(LegPlayerState).where(LegPlayerState.leg_id == leg.id)
        )
    }
    active_id = _expected_player_id(leg, sum(s.turns_taken for s in states.values()))
    active = session.get(Player, active_id)
    if not active.is_bot:
        raise NotBotsTurn("It is a human player's turn, not the bot's.")

    darts = generate_bot_darts(match, states[active_id], active, rng or random.Random())
    turn, match = record_match_visit(session, user, match_id, active_id, darts)
    return turn, match, darts


def generate_bot_darts(
    match: Match, state: LegPlayerState, player: Player, rng: random.Random
) -> list[DartInput]:
    accuracy = bot.ACCURACY[BotDifficulty(player.bot_difficulty)]
    if match.game_type is GameType.CRICKET:
        return bot.cricket_visit(marks_from_game_state(state.game_state), accuracy, rng)
    if match.game_type is GameType.HALVE_IT:
        _, round_number = halve_it_state(state.game_state)
        return bot.halve_it_visit(round_number, accuracy, rng)
    return bot.x01_visit(state.remaining_score, accuracy, rng)


def abandon_match(session: Session, user: User, match_id: uuid.UUID) -> Match:
    """Cancel an in-progress match. No winner is recorded, and
    cancelled matches are excluded from win statistics. The active
    leg keeps its in-progress rows untouched for audit; the cancelled
    match status is what blocks any further scoring."""
    match = get_match(session, match_id)
    ensure_match_access(session, user, match)

    if match.status is not MatchStatus.IN_PROGRESS:
        raise MatchNotActive(f"Match is {match.status}; only an in-progress match can be abandoned.")

    match.status = MatchStatus.CANCELLED
    match.completed_at = datetime.now(timezone.utc)
    session.flush()
    return match


def undo_latest_visit(session: Session, user: User, match_id: uuid.UUID) -> Match:
    """Remove the most recent visit in the active leg and restore the
    scoreboard (spec 13.4: latest active-leg visit only — completed
    legs are immutable in the MVP).

    Against a bot, "undo" means undoing the human's last visit: if the
    latest visit is the bot's reply, both it and the human visit before
    it are removed, so the human is back on the score they want to
    re-enter rather than watching the bot simply throw again.
    """
    match = get_match(session, match_id)
    ensure_match_access(session, user, match)

    if match.status is not MatchStatus.IN_PROGRESS:
        raise MatchNotActive(f"Match is {match.status}; undo is not allowed.")

    leg = next(
        (leg for leg in match.legs if leg.status is LegStatus.IN_PROGRESS), None
    )
    if leg is None:
        raise LegNotActive("The match has no active leg.")

    latest = _latest_turn(session, leg)
    if latest is None:
        raise UndoNotAvailable(
            "No visit exists in the active leg to undo. Completed legs "
            "cannot be modified."
        )

    _remove_turn(session, match, leg, latest)

    if session.get(Player, latest.player_id).is_bot:
        previous = _latest_turn(session, leg)
        if previous is not None and not session.get(Player, previous.player_id).is_bot:
            _remove_turn(session, match, leg, previous)

    session.flush()
    return match


def _latest_turn(session: Session, leg: Leg) -> Turn | None:
    return session.scalars(
        select(Turn)
        .where(Turn.leg_id == leg.id)
        .order_by(Turn.turn_number.desc())
        .limit(1)
    ).first()


def _remove_turn(session: Session, match: Match, leg: Leg, turn: Turn) -> None:
    state = session.scalar(
        select(LegPlayerState).where(
            LegPlayerState.leg_id == leg.id,
            LegPlayerState.player_id == turn.player_id,
        )
    )
    state.darts_thrown -= len(turn.dart_throws)
    state.turns_taken -= 1

    for dart in turn.dart_throws:
        session.delete(dart)
    session.delete(turn)
    session.flush()

    if match.game_type is GameType.CRICKET:
        # Marks aren't reversible per turn; rebuild them by replaying the
        # player's surviving darts — the raw events are the truth.
        state.game_state = _replay_cricket_marks(session, leg.id, turn.player_id)
    elif match.game_type is GameType.HALVE_IT:
        state.game_state = _replay_halve_it(session, leg.id, turn.player_id)
    else:
        state.remaining_score = turn.turn_start_score

    session.flush()


def _replay_halve_it(
    session: Session, leg_id: uuid.UUID, player_id: uuid.UUID
) -> dict:
    rows = session.execute(
        select(
            Turn.turn_number,
            DartThrow.segment,
            DartThrow.multiplier,
            DartThrow.single_band,
        )
        .join(Turn, DartThrow.turn_id == Turn.id)
        .where(Turn.leg_id == leg_id, Turn.player_id == player_id)
        .order_by(Turn.turn_number, DartThrow.dart_number)
    ).all()

    visits: dict[int, list[DartInput]] = {}
    for turn_number, segment, multiplier, band in rows:
        visits.setdefault(turn_number, []).append(
            DartInput(
                segment=None if segment == "MISS" else int(segment),
                multiplier=Multiplier(multiplier),
                band=band,
            )
        )

    score, round_number = HALVE_IT_STARTING_SCORE, 1
    for turn_number in sorted(visits):
        score = apply_halve_it_visit(score, round_number, visits[turn_number]).new_score
        round_number += 1
    return {"score": score, "round": round_number}


def _replay_cricket_marks(
    session: Session, leg_id: uuid.UUID, player_id: uuid.UUID
) -> dict:
    rows = session.execute(
        select(DartThrow.segment, DartThrow.multiplier)
        .join(Turn, DartThrow.turn_id == Turn.id)
        .where(Turn.leg_id == leg_id, Turn.player_id == player_id)
        .order_by(Turn.turn_number, DartThrow.dart_number)
    ).all()

    marks = initial_marks()
    for segment, multiplier in rows:
        dart = DartInput(
            segment=None if segment == "MISS" else int(segment),
            multiplier=Multiplier(multiplier),
        )
        marks = apply_cricket_dart(marks, dart).marks
    return {str(t): c for t, c in marks.items()}


def build_match_state(session: Session, match: Match) -> dict:
    """Assemble the authoritative scoreboard for MatchStateResponse."""
    current_leg = next(
        (leg for leg in match.legs if leg.status is LegStatus.IN_PROGRESS), None
    )
    # After completion there is no active leg, but the final boards
    # (scores/marks) should still come from the last leg played.
    display_leg = current_leg or (match.legs[-1] if match.legs else None)

    states: dict[uuid.UUID, LegPlayerState] = {}
    active_player_id = None
    if display_leg is not None:
        states = {
            s.player_id: s
            for s in session.scalars(
                select(LegPlayerState).where(LegPlayerState.leg_id == display_leg.id)
            )
        }
    if current_leg is not None:
        total_turns = sum(s.turns_taken for s in states.values())
        active_player_id = _expected_player_id(current_leg, total_turns)

    is_cricket = match.game_type is GameType.CRICKET
    is_halve_it = match.game_type is GameType.HALVE_IT
    players = []
    for player_id in (match.player1_id, match.player2_id):
        player = session.get(Player, player_id)
        state = states.get(player_id)
        entry = {
            "player_id": player_id,
            "display_name": player.display_name,
            "legs_won": sum(
                1 for leg in match.legs if leg.winner_player_id == player_id
            ),
            "remaining_score": (
                state.remaining_score
                if state and not is_cricket and not is_halve_it
                else None
            ),
            "marks": (
                marks_from_game_state(state.game_state)
                if state and is_cricket
                else None
            ),
            "bot_difficulty": player.bot_difficulty,
            "is_active_turn": player_id == active_player_id,
        }
        if is_halve_it and state:
            score, round_number = halve_it_state(state.game_state)
            entry["score"] = score
            entry["round"] = round_number
            entry["round_target"] = round_for_number(round_number).value
        players.append(entry)

    return {
        "id": match.id,
        "game_type": match.game_type,
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


@dataclass
class _VisitOutcome:
    """Uniform result of applying a visit's darts under any game mode."""

    turn_start: int
    turn_end: int
    points: int
    is_bust: bool
    leg_won: bool
    dart_rows: list[dict] = field(default_factory=list)
    new_remaining: int | None = None  # x01 only
    new_game_state: dict | None = None  # cricket marks (string keys)


def _play_x01_visit(turn_start: int, darts: list[DartInput]) -> _VisitOutcome:
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

    dart_rows = []
    score_before = turn_start
    for dart, result in zip(darts, results):
        dart_rows.append(
            {
                "segment": "MISS" if dart.segment is None else str(dart.segment),
                "multiplier": dart.multiplier.value,
                "score": result.dart_score,
                "is_double": dart.is_double,
                "is_checkout_attempt": _is_double_finishable(score_before),
                "is_winning_dart": result.is_checkout,
            }
        )
        score_before = result.tentative_remaining if not result.is_bust else score_before

    return _VisitOutcome(
        turn_start=turn_start,
        turn_end=final.effective_remaining,
        points=0 if final.is_bust else turn_start - final.effective_remaining,
        is_bust=final.is_bust,
        leg_won=final.is_checkout,
        dart_rows=dart_rows,
        new_remaining=final.effective_remaining,
    )


def marks_from_game_state(game_state: dict | None) -> dict[int, int]:
    """JSON storage stringifies the mark keys; convert back to ints."""
    if not game_state:
        return initial_marks()
    return {int(target): count for target, count in game_state.items()}


def _play_cricket_visit(
    state: LegPlayerState, darts: list[DartInput]
) -> _VisitOutcome:
    marks = marks_from_game_state(state.game_state)
    dart_rows = []
    won = False
    for index, dart in enumerate(darts):
        result = apply_cricket_dart(marks, dart)
        marks = result.marks
        won = result.leg_won
        if won and index < len(darts) - 1:
            raise InvalidTurn("No darts may follow the leg-winning dart.")
        dart_rows.append(
            {
                "segment": "MISS" if dart.segment is None else str(dart.segment),
                "multiplier": dart.multiplier.value,
                "score": dart.score,
                "is_double": dart.is_double,
                "is_checkout_attempt": False,
                # The 501 constraint requires winning darts to be doubles,
                # so Cricket wins are recorded at the leg level instead.
                "is_winning_dart": False,
            }
        )

    if not won and len(darts) < MAX_DARTS_PER_TURN:
        raise InvalidTurn(
            "A Cricket turn must contain three darts unless it wins the leg."
        )

    return _VisitOutcome(
        # Cricket has no running score; zeros satisfy the turn-table
        # invariants (start == end, points == start - end).
        turn_start=0,
        turn_end=0,
        points=0,
        is_bust=False,
        leg_won=won,
        dart_rows=dart_rows,
        new_game_state={str(t): c for t, c in marks.items()},
    )


def halve_it_state(game_state: dict | None) -> tuple[int, int]:
    """(score, next round number) from stored state."""
    if not game_state:
        return HALVE_IT_STARTING_SCORE, 1
    return (
        int(game_state.get("score", HALVE_IT_STARTING_SCORE)),
        int(game_state.get("round", 1)),
    )


def _play_halve_it_visit(
    state: LegPlayerState, darts: list[DartInput]
) -> _VisitOutcome:
    if len(darts) != DARTS_PER_ROUND:
        raise InvalidTurn("A Halve It round is exactly three darts.")

    score, round_number = halve_it_state(state.game_state)
    result = apply_halve_it_visit(score, round_number, darts)

    dart_rows = [
        {
            "segment": "MISS" if dart.segment is None else str(dart.segment),
            "multiplier": dart.multiplier.value,
            "score": dart.score,
            "is_double": dart.is_double,
            "single_band": dart.band,
            "is_checkout_attempt": False,
            "is_winning_dart": False,
        }
        for dart in darts
    ]

    return _VisitOutcome(
        # Zeros as in Cricket: the running score lives in game_state and
        # is fully rebuildable from the banded raw darts (whether a
        # round halved is derivable the same way, so no flag is stored).
        turn_start=0,
        turn_end=0,
        points=0,
        is_bust=False,
        leg_won=False,  # decided against the opponent's state by the caller
        dart_rows=dart_rows,
        new_game_state={"score": result.new_score, "round": round_number + 1},
    )


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

    # FOR UPDATE serializes concurrent scoring on the same leg (dev
    # plan 8.2: "lock/read active match + leg"). A second concurrent
    # visit waits here, then sees the updated turn count and gets a
    # correct turn-order verdict instead of colliding on turn_number.
    states = {
        s.player_id: s
        for s in session.scalars(
            select(LegPlayerState)
            .where(LegPlayerState.leg_id == leg.id)
            .with_for_update()
        )
    }
    state = states[player_id]
    total_turns = sum(s.turns_taken for s in states.values())
    expected = _expected_player_id(leg, total_turns)
    if player_id != expected:
        raise NotPlayersTurn(f"It is not player {player_id}'s turn.")

    if match.game_type is GameType.CRICKET:
        outcome = _play_cricket_visit(state, darts)
        leg_winner_id = player_id if outcome.leg_won else None
    elif match.game_type is GameType.HALVE_IT:
        outcome = _play_halve_it_visit(state, darts)
        leg_winner_id = _halve_it_leg_winner(states, player_id, outcome)
        outcome.leg_won = leg_winner_id is not None
    else:
        outcome = _play_x01_visit(state.remaining_score, darts)
        leg_winner_id = player_id if outcome.leg_won else None

    now = datetime.now(timezone.utc)
    turn = Turn(
        leg_id=leg.id,
        player_id=player_id,
        turn_number=total_turns + 1,
        turn_start_score=outcome.turn_start,
        turn_end_score=outcome.turn_end,
        points_scored=outcome.points,
        is_bust=outcome.is_bust,
        is_checkout=outcome.leg_won,
    )
    session.add(turn)
    session.flush()  # assign turn.id before darts reference it

    for index, row in enumerate(outcome.dart_rows, start=1):
        session.add(DartThrow(turn_id=turn.id, dart_number=index, **row))

    if outcome.new_remaining is not None:
        state.remaining_score = outcome.new_remaining
    if outcome.new_game_state is not None:
        state.game_state = outcome.new_game_state
    state.darts_thrown += len(darts)
    state.turns_taken += 1

    if outcome.leg_won:
        # In Halve It the leg's winner is not necessarily the thrower.
        states[leg_winner_id].has_won = True
        leg.status = LegStatus.COMPLETED
        leg.winner_player_id = leg_winner_id
        leg.completed_at = now

        legs_won = sum(
            1
            for completed_leg in match.legs
            if completed_leg.winner_player_id == leg_winner_id
        )
        if legs_won >= match.legs_required_to_win:
            match.status = MatchStatus.COMPLETED
            match.winner_player_id = leg_winner_id
            match.completed_at = now

    session.flush()
    return turn
