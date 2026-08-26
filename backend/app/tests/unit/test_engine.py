"""Unit tests for the pure 501 scoring engine.

Covers the Phase 0 acceptance test matrix (spec section 19, S01-S16)
plus dart-representation validation and engine guard rails.

S15 (reject a fourth dart in a turn) and the request-level half of S16
(reject darts against a completed leg) are turn-service rules and will
be tested when that service is built; the engine-level guard for a
finished leg is covered here.
"""

import pytest

from app.scoring.domain import (
    DartInput,
    Multiplier,
    double,
    inner_bull,
    miss,
    outer_bull,
    single,
    triple,
)
from app.scoring.engine import DartResult, apply_dart


def play_turn(turn_start_score: int, darts: list[DartInput]) -> DartResult:
    """Feed darts through one turn the way the turn service will.

    Applies darts in order until the engine says the turn ends
    (bust or checkout) or the darts run out; returns the last result.
    """
    remaining = turn_start_score
    result = None
    for dart in darts:
        result = apply_dart(turn_start_score, remaining, dart)
        if result.turn_should_end:
            return result
        remaining = result.effective_remaining
    assert result is not None, "play_turn requires at least one dart"
    return result


# --- Acceptance matrix S01-S14 -------------------------------------------


def test_s01_t20_from_501_continues_at_441():
    result = apply_dart(501, 501, triple(20))
    assert not result.is_bust
    assert not result.is_checkout
    assert result.effective_remaining == 441
    assert not result.turn_should_end


def test_s02_checkout_on_second_dart_from_60():
    result = play_turn(60, [single(20), double(20)])
    assert result.is_checkout
    assert result.effective_remaining == 0


def test_s03_reaching_zero_on_single_busts_and_restores_40():
    result = play_turn(40, [single(20), single(20)])
    assert result.is_bust
    assert result.effective_remaining == 40


def test_s04_leaving_one_busts_and_restores_32():
    result = play_turn(32, [single(16), single(15)])
    assert result.is_bust
    assert result.effective_remaining == 32


def test_s05_inner_bull_checks_out_from_50():
    result = apply_dart(50, 50, inner_bull())
    assert result.is_checkout
    assert result.effective_remaining == 0


def test_s06_outer_bull_from_25_busts():
    result = apply_dart(25, 25, outer_bull())
    assert result.is_bust
    assert result.effective_remaining == 25


def test_s07_d1_checks_out_from_2():
    result = apply_dart(2, 2, double(1))
    assert result.is_checkout
    assert result.effective_remaining == 0


def test_s08_single_1_from_2_busts_and_restores_2():
    result = apply_dart(2, 2, single(1))
    assert result.is_bust
    assert result.effective_remaining == 2


def test_s09_two_dart_checkout_from_3():
    result = play_turn(3, [single(1), double(1)])
    assert result.is_checkout
    assert result.effective_remaining == 0


def test_s10_single_2_from_3_busts_immediately():
    result = apply_dart(3, 3, single(2))
    assert result.is_bust
    assert result.effective_remaining == 3
    assert result.turn_should_end


def test_s11_t20_d20_checks_out_from_100():
    result = play_turn(100, [triple(20), double(20)])
    assert result.is_checkout
    assert result.effective_remaining == 0


def test_s12_reaching_zero_on_single_busts_and_restores_100():
    result = play_turn(100, [triple(20), single(20), single(20)])
    assert result.is_bust
    assert result.effective_remaining == 100


def test_s13_170_finish_t20_t20_bull():
    result = play_turn(170, [triple(20), triple(20), inner_bull()])
    assert result.is_checkout
    assert result.effective_remaining == 0


def test_s14_fifty_points_as_non_double_cannot_be_represented():
    # 50 points from one dart only exists as the inner bull (double 25).
    with pytest.raises(ValueError):
        DartInput(segment=50, multiplier=Multiplier.SINGLE)


# --- Engine-level guard for finished/impossible states (S16) -------------


@pytest.mark.parametrize("remaining", [0, 1, -5])
def test_engine_rejects_impossible_remaining_scores(remaining):
    with pytest.raises(ValueError):
        apply_dart(501, remaining, single(20))


def test_engine_rejects_mid_turn_score_above_turn_start():
    with pytest.raises(ValueError):
        apply_dart(100, 140, single(20))


# --- Bust rules beyond the matrix ----------------------------------------


def test_going_below_zero_busts():
    result = apply_dart(20, 20, triple(7))  # scores 21
    assert result.is_bust
    assert result.tentative_remaining == -1
    assert result.effective_remaining == 20


def test_bust_on_third_dart_restores_turn_start_not_mid_turn_score():
    # 100 -> T20 (40 left) -> 20 (20 left) -> T7 scores 21, below zero.
    result = play_turn(100, [triple(20), single(20), triple(7)])
    assert result.is_bust
    assert result.effective_remaining == 100


def test_double_that_overshoots_busts():
    result = apply_dart(20, 20, double(20))  # D20 = 40 from 20
    assert result.is_bust
    assert result.effective_remaining == 20


def test_leaving_one_with_a_double_busts():
    result = apply_dart(31, 31, double(15))  # 30, leaves 1
    assert result.is_bust
    assert result.effective_remaining == 31


def test_miss_scores_zero_and_continues():
    result = apply_dart(40, 40, miss())
    assert not result.is_bust
    assert not result.turn_should_end
    assert result.effective_remaining == 40


def test_miss_never_busts_even_on_a_finish():
    # Missing a double leaves the score unchanged; the turn continues.
    result = play_turn(40, [miss(), miss(), miss()])
    assert not result.is_bust
    assert result.effective_remaining == 40
    assert not result.turn_should_end


def test_normal_three_dart_turn_reduces_score():
    result = play_turn(501, [triple(20), triple(20), triple(20)])  # 180
    assert not result.turn_should_end
    assert result.effective_remaining == 321


def test_checkout_on_first_dart_ends_turn_immediately():
    result = apply_dart(40, 40, double(20))
    assert result.is_checkout
    assert result.turn_should_end


# --- Dart representation validation (domain) ------------------------------


@pytest.mark.parametrize(
    "make_dart",
    [
        lambda: triple(25),  # bull has no triple ring
        lambda: single(21),
        lambda: double(0),
        lambda: single(-1),
        lambda: DartInput(segment=20, multiplier=Multiplier.MISS),
        lambda: DartInput(segment=None, multiplier=Multiplier.SINGLE),
    ],
)
def test_illegal_darts_cannot_be_constructed(make_dart):
    with pytest.raises(ValueError):
        make_dart()


@pytest.mark.parametrize(
    "dart, expected_score, expected_is_double",
    [
        (miss(), 0, False),
        (single(20), 20, False),
        (double(20), 40, True),
        (triple(20), 60, False),
        (single(1), 1, False),
        (double(1), 2, True),
        (outer_bull(), 25, False),
        (inner_bull(), 50, True),
    ],
)
def test_dart_scores_and_double_status(dart, expected_score, expected_is_double):
    assert dart.score == expected_score
    assert dart.is_double is expected_is_double
