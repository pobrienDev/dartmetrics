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

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.common.errors import InvalidRequest
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


def _round(value: float | None) -> float | None:
    return None if value is None else round(value, 2)


def head_to_head(
    session: Session, player_id: uuid.UUID, opponent_id: uuid.UUID
) -> dict:
    """Completed-match record between two players, from either side."""
    if player_id == opponent_id:
        raise InvalidRequest("Head-to-head requires two different players.")

    player = get_player(session, player_id)
    opponent = get_player(session, opponent_id)

    pair = (
        (Match.player1_id == player_id) & (Match.player2_id == opponent_id)
    ) | ((Match.player1_id == opponent_id) & (Match.player2_id == player_id))

    matches_played, player_wins, opponent_wins, last_played_at = session.execute(
        select(
            func.count(Match.id),
            func.count(case((Match.winner_player_id == player_id, 1))),
            func.count(case((Match.winner_player_id == opponent_id, 1))),
            func.max(Match.completed_at),
        ).where(Match.status == MatchStatus.COMPLETED, pair)
    ).one()

    player_legs, opponent_legs = session.execute(
        select(
            func.count(case((Leg.winner_player_id == player_id, 1))),
            func.count(case((Leg.winner_player_id == opponent_id, 1))),
        )
        .join(Match, Leg.match_id == Match.id)
        .where(
            Leg.status == LegStatus.COMPLETED,
            Match.status == MatchStatus.COMPLETED,
            pair,
        )
    ).one()

    return {
        "player": {
            "player_id": player.id,
            "display_name": player.display_name,
            "matches_won": player_wins,
            "legs_won": player_legs,
        },
        "opponent": {
            "player_id": opponent.id,
            "display_name": opponent.display_name,
            "matches_won": opponent_wins,
            "legs_won": opponent_legs,
        },
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
        in_match = Turn.player_id == player_id, Leg.match_id == match.id

        points, highest, c100, c140, c180 = session.execute(
            select(
                func.coalesce(func.sum(Turn.points_scored), 0),
                func.max(case((Turn.is_bust.is_(False), Turn.points_scored))),
                func.count(
                    case(
                        (
                            Turn.is_bust.is_(False)
                            & Turn.points_scored.between(100, 139),
                            1,
                        )
                    )
                ),
                func.count(
                    case(
                        (
                            Turn.is_bust.is_(False)
                            & Turn.points_scored.between(140, 179),
                            1,
                        )
                    )
                ),
                func.count(
                    case((Turn.is_bust.is_(False) & (Turn.points_scored == 180), 1))
                ),
            )
            .join(Leg, Turn.leg_id == Leg.id)
            .where(*in_match)
        ).one()

        darts, attempts, successes = session.execute(
            select(
                func.count(DartThrow.id),
                func.count(case((DartThrow.is_checkout_attempt.is_(True), 1))),
                func.count(case((DartThrow.is_winning_dart.is_(True), 1))),
            )
            .join(Turn, DartThrow.turn_id == Turn.id)
            .join(Leg, Turn.leg_id == Leg.id)
            .where(*in_match)
        ).one()

        players.append(
            {
                "player_id": player.id,
                "display_name": player.display_name,
                "legs_won": sum(
                    1 for leg in match.legs if leg.winner_player_id == player_id
                ),
                "darts_thrown": darts,
                "points_scored": points,
                "three_dart_average": _round(points / darts * 3 if darts else None),
                "highest_visit": highest,
                "count_100_plus": c100,
                "count_140_plus": c140,
                "count_180": c180,
                "checkout_attempts": attempts,
                "checkout_successes": successes,
                "checkout_percentage": _round(
                    successes / attempts * 100 if attempts else None
                ),
            }
        )

    # Leg-by-leg results with each player's dart count, for the
    # match summary screen. Abandoned legs are listed as they stand.
    leg_states = session.execute(
        select(LegPlayerState.leg_id, LegPlayerState.player_id, LegPlayerState.darts_thrown)
        .join(Leg, LegPlayerState.leg_id == Leg.id)
        .where(Leg.match_id == match.id)
    ).all()
    darts_by_leg: dict[uuid.UUID, dict[uuid.UUID, int]] = {}
    for leg_id, player_id, darts_thrown in leg_states:
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
    player: Player = get_player(session, player_id)

    # --- turn aggregates ---------------------------------------------
    total_points, highest_visit, c100, c140, c180 = session.execute(
        select(
            func.coalesce(func.sum(Turn.points_scored), 0),
            func.max(case((Turn.is_bust.is_(False), Turn.points_scored))),
            func.count(
                case(
                    (
                        Turn.is_bust.is_(False)
                        & Turn.points_scored.between(100, 139),
                        1,
                    )
                )
            ),
            func.count(
                case(
                    (
                        Turn.is_bust.is_(False)
                        & Turn.points_scored.between(140, 179),
                        1,
                    )
                )
            ),
            func.count(
                case((Turn.is_bust.is_(False) & (Turn.points_scored == 180), 1))
            ),
        )
        .join(Leg, Turn.leg_id == Leg.id)
        .join(Match, Leg.match_id == Match.id)
        .where(Turn.player_id == player_id, _X01_ONLY)
    ).one()

    total_darts = session.scalar(
        select(func.count(DartThrow.id))
        .join(Turn, DartThrow.turn_id == Turn.id)
        .join(Leg, Turn.leg_id == Leg.id)
        .join(Match, Leg.match_id == Match.id)
        .where(Turn.player_id == player_id, _X01_ONLY)
    )

    checkout_attempts, checkout_successes = session.execute(
        select(
            func.count(case((DartThrow.is_checkout_attempt.is_(True), 1))),
            func.count(case((DartThrow.is_winning_dart.is_(True), 1))),
        )
        .join(Turn, DartThrow.turn_id == Turn.id)
        .join(Leg, Turn.leg_id == Leg.id)
        .join(Match, Leg.match_id == Match.id)
        .where(Turn.player_id == player_id, _X01_ONLY)
    ).one()

    # --- match / leg aggregates --------------------------------------
    matches_played, matches_won = session.execute(
        select(
            func.count(Match.id),
            func.count(case((Match.winner_player_id == player_id, 1))),
        ).where(
            Match.status == MatchStatus.COMPLETED,
            (Match.player1_id == player_id) | (Match.player2_id == player_id),
            _X01_ONLY,
        )
    ).one()

    legs_played, legs_won = session.execute(
        select(
            func.count(Leg.id),
            func.count(case((Leg.winner_player_id == player_id, 1))),
        )
        .join(Match, Leg.match_id == Match.id)
        .where(
            Leg.status == LegStatus.COMPLETED,
            (Match.player1_id == player_id) | (Match.player2_id == player_id),
            _X01_ONLY,
        )
    ).one()

    best_leg_darts = session.scalar(
        select(func.count(DartThrow.id))
        .join(Turn, DartThrow.turn_id == Turn.id)
        .join(Leg, Turn.leg_id == Leg.id)
        .join(Match, Leg.match_id == Match.id)
        .where(Turn.player_id == player_id, Leg.winner_player_id == player_id, _X01_ONLY)
        .group_by(Leg.id)
        .order_by(func.count(DartThrow.id))
        .limit(1)
    )

    # --- first-nine average (python-side, per leg) --------------------
    rows = session.execute(
        select(
            Turn.leg_id,
            Turn.turn_number,
            Turn.points_scored,
            func.count(DartThrow.id).label("darts"),
        )
        .join(DartThrow, DartThrow.turn_id == Turn.id)
        .join(Leg, Turn.leg_id == Leg.id)
        .join(Match, Leg.match_id == Match.id)
        .where(Turn.player_id == player_id, _X01_ONLY)
        .group_by(Turn.id, Turn.leg_id, Turn.turn_number, Turn.points_scored)
        .order_by(Turn.leg_id, Turn.turn_number)
    ).all()

    legs: dict[uuid.UUID, list] = {}
    for leg_id, _, points, darts in rows:
        legs.setdefault(leg_id, []).append((points, darts))

    first_nine_points = 0
    first_nine_darts = 0
    for visits in legs.values():
        if sum(d for _, d in visits) < 9:
            continue  # spec: only legs with a meaningful first nine
        darts_counted = 0
        for points, darts in visits:
            if darts_counted >= 9:
                break
            first_nine_points += points
            first_nine_darts += darts
            darts_counted += darts

    return {
        "player_id": player.id,
        "display_name": player.display_name,
        "matches_played": matches_played,
        "matches_won": matches_won,
        "win_percentage": _round(
            matches_won / matches_played * 100 if matches_played else None
        ),
        "legs_played": legs_played,
        "legs_won": legs_won,
        "leg_win_percentage": _round(
            legs_won / legs_played * 100 if legs_played else None
        ),
        "best_leg_darts": best_leg_darts,
        "total_darts": total_darts,
        "three_dart_average": _round(
            total_points / total_darts * 3 if total_darts else None
        ),
        "first_nine_average": _round(
            first_nine_points / first_nine_darts * 3 if first_nine_darts else None
        ),
        "highest_visit": highest_visit,
        "count_100_plus": c100,
        "count_140_plus": c140,
        "count_180": c180,
        "checkout_attempts": checkout_attempts,
        "checkout_successes": checkout_successes,
        "checkout_percentage": _round(
            checkout_successes / checkout_attempts * 100 if checkout_attempts else None
        ),
    }
