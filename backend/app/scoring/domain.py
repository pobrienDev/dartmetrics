"""Core value objects for the 501 scoring domain.

These types define what a legal dart *is*. Any DartInput that can be
constructed is guaranteed valid, so the scoring engine never needs to
re-check board legality.

Board model (Phase 0 spec, section 4.2):
- Miss                      -> 0 points
- Single 1-20               -> segment value
- Double 1-20 (D1-D20)      -> 2 x segment value
- Triple 1-20 (T1-T20)      -> 3 x segment value
- Outer bull                -> single 25 (25 points, not a double)
- Inner bull                -> double 25 (50 points, valid checkout dart)
"""

from dataclasses import dataclass
from enum import Enum

# The bull is modeled as segment 25: outer bull = single 25, inner
# bull = double 25. This matches the double-out rule, where the inner
# bull is treated as D25. A triple 25 does not exist on a dartboard.
BULL_SEGMENT = 25

VALID_NUMBER_SEGMENTS = frozenset(range(1, 21))


class Multiplier(Enum):
    MISS = 0
    SINGLE = 1
    DOUBLE = 2
    TRIPLE = 3


@dataclass(frozen=True)
class DartInput:
    """One thrown dart, validated against the physical board.

    segment is None only for a miss. Raises ValueError for any
    combination that does not exist on a real dartboard.
    """

    segment: int | None
    multiplier: Multiplier

    def __post_init__(self) -> None:
        if self.multiplier is Multiplier.MISS:
            if self.segment is not None:
                raise ValueError("A miss cannot have a segment.")
            return

        if self.segment is None:
            raise ValueError(f"A {self.multiplier.name.lower()} requires a segment.")

        if self.segment == BULL_SEGMENT:
            if self.multiplier is Multiplier.TRIPLE:
                raise ValueError("The bull has no triple ring.")
            return

        if self.segment not in VALID_NUMBER_SEGMENTS:
            raise ValueError(
                f"Invalid segment {self.segment}: must be 1-20 or {BULL_SEGMENT} (bull)."
            )

    @property
    def score(self) -> int:
        if self.multiplier is Multiplier.MISS:
            return 0
        assert self.segment is not None
        return self.segment * self.multiplier.value

    @property
    def is_double(self) -> bool:
        """True for D1-D20 and the inner bull — the only legal finishing darts."""
        return self.multiplier is Multiplier.DOUBLE


# Convenience constructors so tests and services read like darts commentary:
# double(20), triple(19), inner_bull(), miss()

def miss() -> DartInput:
    return DartInput(segment=None, multiplier=Multiplier.MISS)


def single(segment: int) -> DartInput:
    return DartInput(segment=segment, multiplier=Multiplier.SINGLE)


def double(segment: int) -> DartInput:
    return DartInput(segment=segment, multiplier=Multiplier.DOUBLE)


def triple(segment: int) -> DartInput:
    return DartInput(segment=segment, multiplier=Multiplier.TRIPLE)


def outer_bull() -> DartInput:
    return DartInput(segment=BULL_SEGMENT, multiplier=Multiplier.SINGLE)


def inner_bull() -> DartInput:
    return DartInput(segment=BULL_SEGMENT, multiplier=Multiplier.DOUBLE)
