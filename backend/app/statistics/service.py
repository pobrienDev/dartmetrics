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

from app.matches.models import DartThrow, Leg, LegStatus, Match, MatchStatus, Turn
from app.players.models import Player
from app.players.service import get_player


def _round(value: float | None) -> float | None:
    return None if value is None else round(value, 2)


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
        ).where(Turn.player_id == player_id)
    ).one()

    total_darts = session.scalar(
        select(func.count(DartThrow.id))
        .join(Turn, DartThrow.turn_id == Turn.id)
        .where(Turn.player_id == player_id)
    )

    checkout_attempts, checkout_successes = session.execute(
        select(
            func.count(case((DartThrow.is_checkout_attempt.is_(True), 1))),
            func.count(case((DartThrow.is_winning_dart.is_(True), 1))),
        )
        .join(Turn, DartThrow.turn_id == Turn.id)
        .where(Turn.player_id == player_id)
    ).one()

    # --- match / leg aggregates --------------------------------------
    matches_played, matches_won = session.execute(
        select(
            func.count(Match.id),
            func.count(case((Match.winner_player_id == player_id, 1))),
        ).where(
            Match.status == MatchStatus.COMPLETED,
            (Match.player1_id == player_id) | (Match.player2_id == player_id),
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
        )
    ).one()

    best_leg_darts = session.scalar(
        select(func.count(DartThrow.id))
        .join(Turn, DartThrow.turn_id == Turn.id)
        .join(Leg, Turn.leg_id == Leg.id)
        .where(Turn.player_id == player_id, Leg.winner_player_id == player_id)
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
        .where(Turn.player_id == player_id)
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
