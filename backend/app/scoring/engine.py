"""Pure 501 scoring engine.

Implements the Phase 0 evaluation order (spec sections 13-14) for a
single dart. No FastAPI, no database — just rules. The turn service
(a later step) is responsible for turn counts, alternation, and
persistence; this module only answers: given a remaining score and a
dart, what happens?

Rules applied here (double-out 501):
- Going below 0 busts the turn.
- Leaving exactly 1 busts the turn (1 cannot be finished on a double).
- Reaching exactly 0 wins the leg only if the dart is a double
  (D1-D20 or inner bull); otherwise the turn busts.
- A bust restores the player to the score they had at the start of
  the turn, discarding all darts thrown this visit.
"""

from dataclasses import dataclass

from app.scoring.domain import DartInput


@dataclass(frozen=True)
class DartResult:
    """Outcome of applying one dart to the current remaining score.

    effective_remaining is the score the player is actually left on:
    the new remaining score for a normal dart, 0 for a checkout, or
    the turn's starting score for a bust.
    """

    dart_score: int
    tentative_remaining: int
    is_bust: bool
    is_checkout: bool
    effective_remaining: int
    turn_should_end: bool


def apply_dart(
    turn_start_score: int,
    current_remaining_score: int,
    dart: DartInput,
) -> DartResult:
    if current_remaining_score < 2:
        # Invariant: an active player is always on 2 or more. 0 means
        # the leg already ended; 1 can never persist under double-out.
        raise ValueError(
            f"current_remaining_score must be >= 2, got {current_remaining_score}."
        )
    if turn_start_score < current_remaining_score:
        raise ValueError(
            "turn_start_score cannot be lower than current_remaining_score."
        )

    points = dart.score
    candidate = current_remaining_score - points

    if candidate < 0 or candidate == 1 or (candidate == 0 and not dart.is_double):
        return DartResult(
            dart_score=points,
            tentative_remaining=candidate,
            is_bust=True,
            is_checkout=False,
            effective_remaining=turn_start_score,
            turn_should_end=True,
        )

    if candidate == 0:
        return DartResult(
            dart_score=points,
            tentative_remaining=0,
            is_bust=False,
            is_checkout=True,
            effective_remaining=0,
            turn_should_end=True,
        )

    return DartResult(
        dart_score=points,
        tentative_remaining=candidate,
        is_bust=False,
        is_checkout=False,
        effective_remaining=candidate,
        turn_should_end=False,
    )
