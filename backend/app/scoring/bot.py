"""Bot opponents: a pure throw simulator plus per-game aiming strategy.

Nothing here touches the database. Given a game situation, a
difficulty, and a random source, the module answers: what darts would
the bot throw this visit? The turn service then records them exactly
as if a human had entered them, so bot visits flow through the same
engines, constraints, and statistics as everything else.

Two layers:

1. Aiming (deterministic): where a sensible player would aim next in
   this situation — T20 while scoring, the right double when a finish
   is on, a setup shot that leaves a good double, the highest open
   Cricket target, the current Halve It round's target.
2. Throwing (random): where the dart actually lands, driven by the
   difficulty's accuracy. A missed triple usually drops into the big
   single of the same segment; wilder misses wander into the
   neighbouring segments; the worst players miss the board entirely.

Difficulties are ordered noob < easy < medium < hard < pro. Their
accuracies were tuned so a bot aiming at T20 averages roughly 32, 47,
63, 81, and 100 per three darts respectively. The plain-single rates
are not pinned by that tuning (scoring visits aim at the triple), so
they follow a throw-scatter model instead: a ~47-average thrower hits
the big single they aim at about 45% of the time, a ~32-average one
about 35%. Halve It's band rounds run entirely on those rates.
"""

import random
from dataclasses import dataclass

from app.players.models import BotDifficulty
from app.scoring.cricket import CRICKET_TARGETS, MARKS_TO_CLOSE, apply_cricket_dart
from app.scoring.domain import BULL_SEGMENT, DartInput, Multiplier
from app.scoring.engine import apply_dart
from app.scoring.halve_it import (
    BLACK_SEGMENTS,
    DARTS_PER_ROUND,
    SIXTY_THREE_TARGET,
    WHITE_SEGMENTS,
    HalveItRound,
    round_for_number,
)

# Clockwise segment order around a standard board, used to find the
# neighbours a stray dart lands in.
BOARD_ORDER = (20, 1, 18, 4, 13, 6, 10, 15, 2, 17, 3, 19, 7, 16, 8, 11, 14, 9, 12, 5)


@dataclass(frozen=True)
class Accuracy:
    """Hit probabilities for one difficulty."""

    triple: float  # P(hit the triple when aiming at it)
    double: float  # P(hit the double when aiming at it)
    single: float  # P(hit the intended single when aiming at it)
    inner_bull: float  # P(inner bull when aiming at it)
    outer_bull: float  # P(outer bull when aiming at the inner bull)
    band: float  # P(landing in the intended single band, given a single)
    board_miss: float  # P(missing the board completely)
    scatter: float  # P(a missed ring strays into a neighbouring segment)


ACCURACY: dict[BotDifficulty, Accuracy] = {
    BotDifficulty.NOOB: Accuracy(0.06, 0.07, 0.36, 0.03, 0.12, 0.50, 0.12, 0.65),
    BotDifficulty.EASY: Accuracy(0.11, 0.14, 0.46, 0.06, 0.20, 0.55, 0.05, 0.53),
    BotDifficulty.MEDIUM: Accuracy(0.17, 0.22, 0.75, 0.15, 0.30, 0.70, 0.02, 0.45),
    BotDifficulty.HARD: Accuracy(0.27, 0.35, 0.85, 0.25, 0.38, 0.80, 0.01, 0.35),
    BotDifficulty.PRO: Accuracy(0.40, 0.48, 0.93, 0.38, 0.42, 0.88, 0.00, 0.30),
}


@dataclass(frozen=True)
class Aim:
    """Where the bot is trying to put the dart. A MISS multiplier is a
    deliberate miss (Halve It's 63 round once the total is reached)."""

    segment: int | None
    multiplier: Multiplier
    band: str | None = None


def _neighbour(segment: int, rng: random.Random) -> int:
    index = BOARD_ORDER.index(segment)
    step = rng.choice((-1, 1))
    return BOARD_ORDER[(index + step) % len(BOARD_ORDER)]


def _with_band(segment: int, aim: Aim, accuracy: Accuracy, rng: random.Random) -> DartInput:
    """A single on a numbered segment, carrying a band only when the
    aim cares about bands (Halve It rounds 1-4)."""
    if aim.band is None:
        return DartInput(segment=segment, multiplier=Multiplier.SINGLE)
    other = "inner" if aim.band == "outer" else "outer"
    band = aim.band if rng.random() < accuracy.band else other
    return DartInput(segment=segment, multiplier=Multiplier.SINGLE, band=band)


def throw(aim: Aim, accuracy: Accuracy, rng: random.Random) -> DartInput:
    """Simulate one dart thrown at the aim."""
    if aim.multiplier is Multiplier.MISS:
        return DartInput(segment=None, multiplier=Multiplier.MISS)
    if rng.random() < accuracy.board_miss:
        return DartInput(segment=None, multiplier=Multiplier.MISS)

    assert aim.segment is not None
    if aim.segment == BULL_SEGMENT:
        return _throw_at_bull(aim, accuracy, rng)

    roll = rng.random()
    if aim.multiplier is Multiplier.SINGLE:
        if roll < accuracy.single:
            return _with_band(aim.segment, aim, accuracy, rng)
        # Missed the intended single: mostly a neighbouring single, but
        # the triple ring of either segment is in the way too.
        stray = rng.random()
        if stray < 0.15:
            return DartInput(segment=aim.segment, multiplier=Multiplier.TRIPLE)
        neighbour = _neighbour(aim.segment, rng)
        if stray < 0.25:
            return DartInput(segment=neighbour, multiplier=Multiplier.TRIPLE)
        return _with_band(neighbour, aim, accuracy, rng)

    hit_probability = (
        accuracy.triple if aim.multiplier is Multiplier.TRIPLE else accuracy.double
    )
    if roll < hit_probability:
        return DartInput(segment=aim.segment, multiplier=aim.multiplier)

    # Missed the ring. Either stay in this segment's single, or stray
    # into a neighbour. Landing in the neighbour's ring is about as
    # likely as hitting the ring aimed at: a flat chance here let weak
    # bots collect "any double / any triple" in Halve It almost for free.
    if rng.random() >= accuracy.scatter:
        return _with_band(aim.segment, aim, accuracy, rng)
    neighbour = _neighbour(aim.segment, rng)
    if rng.random() < hit_probability:
        return DartInput(segment=neighbour, multiplier=aim.multiplier)
    return _with_band(neighbour, aim, accuracy, rng)


def _throw_at_bull(aim: Aim, accuracy: Accuracy, rng: random.Random) -> DartInput:
    aiming_inner = aim.multiplier is Multiplier.DOUBLE
    if aiming_inner:
        p_inner, p_outer = accuracy.inner_bull, accuracy.outer_bull
    else:
        # The outer ring is a bigger target; some darts still drop inside.
        # The bonus scales with skill: a flat one made weak bots far too
        # good at Halve It's green-bull round.
        p_inner, p_outer = accuracy.inner_bull * 0.5, accuracy.outer_bull + accuracy.inner_bull * 0.5

    roll = rng.random()
    if roll < p_inner:
        return DartInput(segment=BULL_SEGMENT, multiplier=Multiplier.DOUBLE)
    if roll < p_inner + p_outer:
        return DartInput(segment=BULL_SEGMENT, multiplier=Multiplier.SINGLE)
    # Anywhere in the inner singles ring around the bull.
    return DartInput(segment=rng.choice(BOARD_ORDER), multiplier=Multiplier.SINGLE)


# --- 501 -------------------------------------------------------------------

# Leftovers a finishing player likes to be on, best first: D16 and D20
# have the simplest bail-outs when the double is missed narrowly.
PREFERRED_LEFTOVERS = (
    32, 40, 16, 24, 20, 8, 36, 4, 12, 28, 2, 6, 10, 14, 18, 22, 26, 30, 34, 38, 50,
)


def is_double_finishable(score: int) -> bool:
    return score == 50 or (2 <= score <= 40 and score % 2 == 0)


def _single_dart_for(points: int) -> Aim | None:
    """A dart that scores exactly `points`, preferring the easiest ring."""
    if points < 1:
        return None
    if points <= 20:
        return Aim(points, Multiplier.SINGLE)
    if points == 25:
        return Aim(BULL_SEGMENT, Multiplier.SINGLE)
    if points % 3 == 0 and points // 3 <= 20:
        return Aim(points // 3, Multiplier.TRIPLE)
    if points % 2 == 0 and points // 2 <= 20:
        return Aim(points // 2, Multiplier.DOUBLE)
    if points == 50:
        return Aim(BULL_SEGMENT, Multiplier.DOUBLE)
    return None


def choose_x01_aim(remaining: int) -> Aim:
    """Where to aim with `remaining` left under double-out rules."""
    if is_double_finishable(remaining):
        if remaining == 50:
            return Aim(BULL_SEGMENT, Multiplier.DOUBLE)
        return Aim(remaining // 2, Multiplier.DOUBLE)

    if remaining <= 170:
        # Setup: leave a preferred double with a single dart.
        for leftover in PREFERRED_LEFTOVERS:
            aim = _single_dart_for(remaining - leftover)
            if aim is not None:
                return aim

    # Scoring: the biggest dart that cannot bust or leave 1.
    for segment in (20, 19, 18, 17, 16):
        if remaining - segment * 3 >= 2:
            return Aim(segment, Multiplier.TRIPLE)
    for segment in range(20, 0, -1):
        if remaining - segment >= 2:
            return Aim(segment, Multiplier.SINGLE)
    return Aim(1, Multiplier.SINGLE)  # remaining is 3; leaves 2


def x01_visit(remaining: int, accuracy: Accuracy, rng: random.Random) -> list[DartInput]:
    """Throw up to three darts, stopping on a bust or checkout exactly
    as the engine requires."""
    darts: list[DartInput] = []
    current = remaining
    for _ in range(3):
        dart = throw(choose_x01_aim(current), accuracy, rng)
        darts.append(dart)
        result = apply_dart(remaining, current, dart)
        if result.turn_should_end:
            break
        current = result.effective_remaining
    return darts


# --- Cricket ---------------------------------------------------------------


def choose_cricket_aim(marks: dict[int, int]) -> Aim:
    """Highest open number first, the bull last (it needs the inner ring)."""
    numbers = sorted((t for t in CRICKET_TARGETS if t != BULL_SEGMENT), reverse=True)
    for target in numbers:
        if marks[target] < MARKS_TO_CLOSE:
            return Aim(target, Multiplier.TRIPLE)
    if marks[BULL_SEGMENT] < MARKS_TO_CLOSE:
        return Aim(BULL_SEGMENT, Multiplier.DOUBLE)
    return Aim(20, Multiplier.TRIPLE)  # board closed; unreachable in play


def cricket_visit(
    marks: dict[int, int], accuracy: Accuracy, rng: random.Random
) -> list[DartInput]:
    darts: list[DartInput] = []
    current = dict(marks)
    for _ in range(3):
        dart = throw(choose_cricket_aim(current), accuracy, rng)
        darts.append(dart)
        result = apply_cricket_dart(current, dart)
        current = result.marks
        if result.turn_should_end:
            break
    return darts


# --- Halve It ----------------------------------------------------------------


def _sixty_three_aim(needed: int, darts_left: int) -> Aim:
    """Chase exactly 63 across the round; deliberately miss once there."""
    if needed <= 0:
        return Aim(None, Multiplier.MISS)
    if needed <= 20:
        return Aim(needed, Multiplier.SINGLE)
    if darts_left >= 2:
        # Biggest triple that still leaves something the remaining
        # darts can score.
        for segment in range(20, 0, -1):
            if 3 * segment <= needed and needed - 3 * segment <= 60 * (darts_left - 1):
                return Aim(segment, Multiplier.TRIPLE)
    aim = _single_dart_for(needed)
    return aim if aim is not None else Aim(20, Multiplier.TRIPLE)


def choose_halve_it_aim(
    target: HalveItRound, darts_so_far: list[DartInput]
) -> Aim:
    match target:
        case HalveItRound.OUTER_BLACK:
            return Aim(max(BLACK_SEGMENTS), Multiplier.SINGLE, band="outer")
        case HalveItRound.OUTER_WHITE:
            return Aim(max(WHITE_SEGMENTS), Multiplier.SINGLE, band="outer")
        case HalveItRound.INNER_BLACK:
            return Aim(max(BLACK_SEGMENTS), Multiplier.SINGLE, band="inner")
        case HalveItRound.INNER_WHITE:
            return Aim(max(WHITE_SEGMENTS), Multiplier.SINGLE, band="inner")
        case HalveItRound.DOUBLES:
            return Aim(20, Multiplier.DOUBLE)
        case HalveItRound.TRIPLES:
            return Aim(20, Multiplier.TRIPLE)
        case HalveItRound.SIXTY_THREE:
            scored = sum(dart.score for dart in darts_so_far)
            return _sixty_three_aim(
                SIXTY_THREE_TARGET - scored, DARTS_PER_ROUND - len(darts_so_far)
            )
        case HalveItRound.GREEN_BULL:
            return Aim(BULL_SEGMENT, Multiplier.SINGLE)
        case _:  # RED_BULL and tie-break rounds
            return Aim(BULL_SEGMENT, Multiplier.DOUBLE)


def halve_it_visit(
    round_number: int, accuracy: Accuracy, rng: random.Random
) -> list[DartInput]:
    target = round_for_number(round_number)
    darts: list[DartInput] = []
    for _ in range(DARTS_PER_ROUND):
        darts.append(throw(choose_halve_it_aim(target, darts), accuracy, rng))
    return darts
