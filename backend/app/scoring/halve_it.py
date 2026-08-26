"""Pure Halve It engine — house rules (docs/GAME_MODES.md).

Unlike 501 and Cricket, Halve It is evaluated per complete three-dart
round: qualifying darts add their face value; if none qualify (or the
63 round's total is wrong), the player's score is halved, rounding up.
The round sequence is fixed; ties are broken by extra Red Bull rounds.
"""

import enum
import math
from dataclasses import dataclass

from app.scoring.domain import BULL_SEGMENT, DartInput, Multiplier

# Standard board colouring: segments alternate starting with 20 black.
BLACK_SEGMENTS = frozenset({20, 18, 13, 10, 2, 3, 7, 8, 14, 12})
WHITE_SEGMENTS = frozenset({1, 4, 6, 15, 17, 19, 16, 11, 9, 5})

DARTS_PER_ROUND = 3
SIXTY_THREE_TARGET = 63


class HalveItRound(enum.StrEnum):
    OUTER_BLACK = "outer_black"
    OUTER_WHITE = "outer_white"
    INNER_BLACK = "inner_black"
    INNER_WHITE = "inner_white"
    DOUBLES = "doubles"
    TRIPLES = "triples"
    SIXTY_THREE = "sixty_three"
    GREEN_BULL = "green_bull"
    RED_BULL = "red_bull"


ROUND_SEQUENCE: tuple[HalveItRound, ...] = (
    HalveItRound.OUTER_BLACK,
    HalveItRound.OUTER_WHITE,
    HalveItRound.INNER_BLACK,
    HalveItRound.INNER_WHITE,
    HalveItRound.DOUBLES,
    HalveItRound.TRIPLES,
    HalveItRound.SIXTY_THREE,
    HalveItRound.GREEN_BULL,
    HalveItRound.RED_BULL,
)


def round_for_number(round_number: int) -> HalveItRound:
    """1-based round -> its target. Rounds past 9 are the tie-break:
    more Red Bull."""
    if round_number < 1:
        raise ValueError("round_number is 1-based.")
    if round_number <= len(ROUND_SEQUENCE):
        return ROUND_SEQUENCE[round_number - 1]
    return HalveItRound.RED_BULL


def _band_points(dart: DartInput, band: str, colour: frozenset[int]) -> int:
    if (
        dart.multiplier is Multiplier.SINGLE
        and dart.segment in colour
        and dart.band == band
    ):
        return dart.segment
    return 0


def _dart_points(dart: DartInput, target: HalveItRound) -> int:
    """Face value the dart contributes in this round; 0 if it doesn't
    qualify. (The 63 round is handled at visit level, not here.)"""
    match target:
        case HalveItRound.OUTER_BLACK:
            return _band_points(dart, "outer", BLACK_SEGMENTS)
        case HalveItRound.OUTER_WHITE:
            return _band_points(dart, "outer", WHITE_SEGMENTS)
        case HalveItRound.INNER_BLACK:
            return _band_points(dart, "inner", BLACK_SEGMENTS)
        case HalveItRound.INNER_WHITE:
            return _band_points(dart, "inner", WHITE_SEGMENTS)
        case HalveItRound.DOUBLES:
            # The double RING only: the inner bull is not part of it.
            if dart.multiplier is Multiplier.DOUBLE and dart.segment != BULL_SEGMENT:
                return dart.score
            return 0
        case HalveItRound.TRIPLES:
            return dart.score if dart.multiplier is Multiplier.TRIPLE else 0
        case HalveItRound.GREEN_BULL:
            is_outer_bull = (
                dart.segment == BULL_SEGMENT and dart.multiplier is Multiplier.SINGLE
            )
            return 25 if is_outer_bull else 0
        case HalveItRound.RED_BULL:
            is_inner_bull = (
                dart.segment == BULL_SEGMENT and dart.multiplier is Multiplier.DOUBLE
            )
            return 50 if is_inner_bull else 0
        case _:
            return 0


def halved(score: int) -> int:
    return math.ceil(score / 2)


@dataclass(frozen=True)
class HalveItVisitResult:
    points_scored: int  # what the round added (0 when halved)
    was_halved: bool
    new_score: int


def apply_halve_it_visit(
    score: int, round_number: int, darts: list[DartInput]
) -> HalveItVisitResult:
    """Evaluate one complete round for one player."""
    if len(darts) != DARTS_PER_ROUND:
        raise ValueError("A Halve It round is exactly three darts.")

    target = round_for_number(round_number)

    if target is HalveItRound.SIXTY_THREE:
        total = sum(dart.score for dart in darts)
        if total == SIXTY_THREE_TARGET:
            points = SIXTY_THREE_TARGET
        else:
            return HalveItVisitResult(0, True, halved(score))
    else:
        points = sum(_dart_points(dart, target) for dart in darts)
        if points == 0:
            return HalveItVisitResult(0, True, halved(score))

    return HalveItVisitResult(points, False, score + points)
