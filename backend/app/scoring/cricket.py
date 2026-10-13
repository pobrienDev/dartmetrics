"""Pure Cricket engine — race-to-close variant (docs/GAME_MODES.md).

Targets 15-20 and Bull each need 3 marks. Single = 1 mark, double = 2,
triple = 3; the bull is segment 25 (outer = single = 1 mark, inner =
double = 2). Darts at other segments, or at closed targets, do
nothing. Marks past 3 are discarded (no points). The leg is won by
the dart that closes the last open target.

State is a plain dict {target: marks}, deliberately JSON-friendly for
storage in LegPlayerState.game_state (JSON turns the keys into
strings; the service converts back).
"""

from dataclasses import dataclass

from app.scoring.domain import BULL_SEGMENT, DartInput

CRICKET_TARGETS = (15, 16, 17, 18, 19, 20, BULL_SEGMENT)
MARKS_TO_CLOSE = 3


def initial_marks() -> dict[int, int]:
    return dict.fromkeys(CRICKET_TARGETS, 0)


def is_board_closed(marks: dict[int, int]) -> bool:
    return all(marks[target] >= MARKS_TO_CLOSE for target in CRICKET_TARGETS)


@dataclass(frozen=True)
class CricketDartResult:
    marks: dict[int, int]  # state after the dart (input is not mutated)
    leg_won: bool  # this dart closed the last open target


def apply_cricket_dart(marks: dict[int, int], dart: DartInput) -> CricketDartResult:
    raw_marks = dart.multiplier.value  # miss=0, single=1, double=2, triple=3
    target = dart.segment if dart.segment in CRICKET_TARGETS else None

    if target is None or raw_marks == 0 or marks[target] >= MARKS_TO_CLOSE:
        return CricketDartResult(marks=dict(marks), leg_won=False)

    new_marks = dict(marks)
    new_marks[target] = min(MARKS_TO_CLOSE, marks[target] + raw_marks)
    return CricketDartResult(marks=new_marks, leg_won=is_board_closed(new_marks))
