"""Player statistics computed from raw scoring events (dev plan
section 14, Appendix C; Phase 0 spec section 16).

Everything derives from turns/dart_throws/legs/matches at query time —
no cached aggregates. If a formula changes, history recomputes
automatically. Definitions applied:

- Three-dart average: total effective points / darts thrown * 3.
  Bust turns store points_scored = 0, so bust darts count as thrown
  but score nothing.
- First-nine average: only legs where the player threw at least 9
  darts. Whole visits are accumulated until 9 darts are counted, and
  the average scales by the darts actually counted — so a shortened
  visit near the boundary can never inflate the number.
- Big-visit counts (100+/140+/180) exclude busts.
- Checkout %: winning darts / recorded checkout-attempt darts; None
  when no attempts.
- Win %: completed matches only. Leg win %: completed legs only.
"""

import uuid

from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session

from app.auth.models import User
from app.common.errors import Forbidden, InvalidRequest
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
from app.players.models import Player
from app.players.service import get_player

# player_stats implements the 501 formulas (Appendix C); Cricket and
# Halve It turns must never leak into these aggregates.
_X01_ONLY = Match.game_type == GameType.X01


def _ratio(numerator: int, denominator: int, scale: int) -> float | None:
    """numerator / denominator * scale to two places, or None (never 0%)
    when there is no sample."""
    return round(numerator / denominator * scale, 2) if denominator else None


def _played_by(player_id: uuid.UUID):
    return (Match.player1_id == player_id) | (Match.player2_id == player_id)


def _visit_columns() -> tuple:
    """Points, highest visit and the 100+/140+/180 counts over turns.
    Busts score 0 and are left out of the high and the big-visit counts."""
    scoring = Turn.is_bust.is_(False)
    return (
        func.coalesce(func.sum(Turn.points_scored), 0),
        func.max(case((scoring, Turn.points_scored))),
        func.count(case((scoring & Turn.points_scored.between(100, 139), 1))),
        func.count(case((scoring & Turn.points_scored.between(140, 179), 1))),
        func.count(case((scoring & (Turn.points_scored == 180), 1))),
    )


def _dart_columns() -> tuple:
    """Darts thrown, checkout attempts and checkouts over dart_throws."""
    return (
        func.count(DartThrow.id),
        func.count(case((DartThrow.is_checkout_attempt.is_(True), 1))),
        func.count(case((DartThrow.is_winning_dart.is_(True), 1))),
    )


# Joins follow the foreign keys: dart_throws -> turns -> legs -> matches.
_DARTS = select(DartThrow).select_from(DartThrow).join(Turn).join(Leg).join(Match)
_TURNS = select(Turn).join(Leg).join(Match)


def ensure_stats_access(session: Session, user: User, player_id: uuid.UUID) -> Player:
    """Statistics are private, like match state: readable by the
    profile's owner (the account it is linked to, or the account that
    created the guest) and by anyone who shares a match with the player
    — which is how the shared bots' records stay visible to the people
    who played them. Everyone else gets 403."""
    player = get_player(session, player_id)
    if user.id in (player.user_id, player.created_by_user_id):
        return player

    own_player_ids = select(Player.id).where(Player.user_id == user.id)
    shared_match = session.scalar(
        select(Match.id)
        .where(
            _played_by(player_id),
            or_(
                Match.created_by_user_id == user.id,
                Match.player1_id.in_(own_player_ids),
                Match.player2_id.in_(own_player_ids),
            ),
        )
        .limit(1)
    )
    if shared_match is None:
        raise Forbidden("Statistics are visible to the player and the people they play.")
    return player


def head_to_head(session: Session, player_id: uuid.UUID, opponent_id: uuid.UUID) -> dict:
    """Completed-match record between two players, from either side."""
    if player_id == opponent_id:
        raise InvalidRequest("Head-to-head requires two different players.")

    player = get_player(session, player_id)
    opponent = get_player(session, opponent_id)
    pair = (_played_by(player_id) & _played_by(opponent_id), Match.status == MatchStatus.COMPLETED)

    matches_played, player_wins, opponent_wins, last_played_at = session.execute(
        select(
            func.count(Match.id),
            func.count(case((Match.winner_player_id == player_id, 1))),
            func.count(case((Match.winner_player_id == opponent_id, 1))),
            func.max(Match.completed_at),
        ).where(*pair)
    ).one()

    player_legs, opponent_legs = session.execute(
        select(
            func.count(case((Leg.winner_player_id == player_id, 1))),
            func.count(case((Leg.winner_player_id == opponent_id, 1))),
        )
        .join(Match)
        .where(Leg.status == LegStatus.COMPLETED, *pair)
    ).one()

    def side(p: Player, matches_won: int, legs_won: int) -> dict:
        return {
            "player_id": p.id,
            "display_name": p.display_name,
            "matches_won": matches_won,
            "legs_won": legs_won,
        }

    return {
        "player": side(player, player_wins, player_legs),
        "opponent": side(opponent, opponent_wins, opponent_legs),
        "matches_played": matches_played,
        "last_played_at": last_played_at,
    }


def match_summary(session: Session, match_id: uuid.UUID) -> dict:
    """Per-player performance within one match, from its raw turns.

    Works for matches in any status — for an in-progress match it is
    the live summary so far.
    """
    from app.matches.service import get_match

    match = get_match(session, match_id)

    players = []
    for player_id in (match.player1_id, match.player2_id):
        player = get_player(session, player_id)
        in_match = (Turn.player_id == player_id, Leg.match_id == match.id)

        points, highest, c100, c140, c180 = session.execute(
            _TURNS.with_only_columns(*_visit_columns()).where(*in_match)
        ).one()
        darts, attempts, successes = session.execute(
            _DARTS.with_only_columns(*_dart_columns()).where(*in_match)
        ).one()

        players.append(
            {
                "player_id": player.id,
                "display_name": player.display_name,
                "legs_won": sum(1 for leg in match.legs if leg.winner_player_id == player_id),
                "darts_thrown": darts,
                "points_scored": points,
                "three_dart_average": _ratio(points, darts, 3),
                "highest_visit": highest,
                "count_100_plus": c100,
                "count_140_plus": c140,
                "count_180": c180,
                "checkout_attempts": attempts,
                "checkout_successes": successes,
                "checkout_percentage": _ratio(successes, attempts, 100),
            }
        )

    # Leg-by-leg results with each player's dart count, for the
    # match summary screen. Abandoned legs are listed as they stand.
    darts_by_leg: dict[uuid.UUID, dict[uuid.UUID, int]] = {}
    for leg_id, player_id, darts_thrown in session.execute(
        select(LegPlayerState.leg_id, LegPlayerState.player_id, LegPlayerState.darts_thrown)
        .join(Leg)
        .where(Leg.match_id == match.id)
    ):
        darts_by_leg.setdefault(leg_id, {})[player_id] = darts_thrown
    legs = [
        {
            "leg_number": leg.leg_number,
            "status": leg.status,
            "starting_player_id": leg.starting_player_id,
            "winner_player_id": leg.winner_player_id,
            "darts_thrown": {
                str(pid): darts_by_leg.get(leg.id, {}).get(pid, 0)
                for pid in (match.player1_id, match.player2_id)
            },
        }
        for leg in match.legs
    ]

    return {
        "id": match.id,
        "game_type": match.game_type,
        "status": match.status,
        "best_of_legs": match.best_of_legs,
        "winner_player_id": match.winner_player_id,
        "started_at": match.started_at,
        "completed_at": match.completed_at,
        "players": players,
        "legs": legs,
    }


def player_stats(session: Session, player_id: uuid.UUID) -> dict:
    player = get_player(session, player_id)
    # Every aggregate below is over the player's own 501 turns and darts.
    own = (Turn.player_id == player_id, _X01_ONLY)

    total_points, highest_visit, c100, c140, c180 = session.execute(
        _TURNS.with_only_columns(*_visit_columns()).where(*own)
    ).one()
    total_darts, checkout_attempts, checkout_successes = session.execute(
        _DARTS.with_only_columns(*_dart_columns()).where(*own)
    ).one()

    matches_played, matches_won = session.execute(
        select(
            func.count(Match.id),
            func.count(case((Match.winner_player_id == player_id, 1))),
        ).where(Match.status == MatchStatus.COMPLETED, _played_by(player_id), _X01_ONLY)
    ).one()
    legs_played, legs_won = session.execute(
        select(
            func.count(Leg.id),
            func.count(case((Leg.winner_player_id == player_id, 1))),
        )
        .join(Match)
        .where(Leg.status == LegStatus.COMPLETED, _played_by(player_id), _X01_ONLY)
    ).one()

    best_leg_darts = session.scalar(
        _DARTS.with_only_columns(func.count(DartThrow.id))
        .where(*own, Leg.winner_player_id == player_id)
        .group_by(Leg.id)
        .order_by(func.count(DartThrow.id))
        .limit(1)
    )

    # First-nine average: python-side, per leg (see the module docstring).
    visits_by_leg: dict[uuid.UUID, list[tuple[int, int]]] = {}
    for leg_id, points, darts in session.execute(
        _DARTS.with_only_columns(Turn.leg_id, Turn.points_scored, func.count(DartThrow.id))
        .where(*own)
        .group_by(Turn.id, Turn.leg_id, Turn.turn_number, Turn.points_scored)
        .order_by(Turn.leg_id, Turn.turn_number)
    ):
        visits_by_leg.setdefault(leg_id, []).append((points, darts))

    first_nine_points = first_nine_darts = 0
    for visits in visits_by_leg.values():
        if sum(d for _, d in visits) < 9:
            continue  # spec: only legs with a meaningful first nine
        counted = 0
        for points, darts in visits:
            if counted >= 9:
                break
            first_nine_points += points
            first_nine_darts += darts
            counted += darts

    return {
        "player_id": player.id,
        "display_name": player.display_name,
        "matches_played": matches_played,
        "matches_won": matches_won,
        "win_percentage": _ratio(matches_won, matches_played, 100),
        "legs_played": legs_played,
        "legs_won": legs_won,
        "leg_win_percentage": _ratio(legs_won, legs_played, 100),
        "best_leg_darts": best_leg_darts,
        "total_darts": total_darts,
        "three_dart_average": _ratio(total_points, total_darts, 3),
        "first_nine_average": _ratio(first_nine_points, first_nine_darts, 3),
        "highest_visit": highest_visit,
        "count_100_plus": c100,
        "count_140_plus": c140,
        "count_180": c180,
        "checkout_attempts": checkout_attempts,
        "checkout_successes": checkout_successes,
        "checkout_percentage": _ratio(checkout_successes, checkout_attempts, 100),
    }
