"""Unit tests for the Halve It engine — mirrors the acceptance table
in docs/GAME_MODES.md."""

import pytest

from app.scoring.domain import DartInput, Multiplier, double, inner_bull, miss, outer_bull, single, triple
from app.scoring.halve_it import (
    HalveItRound,
    ROUND_SEQUENCE,
    apply_halve_it_visit,
    halved,
    round_for_number,
)


def banded(segment: int, band: str) -> DartInput:
    return DartInput(segment=segment, multiplier=Multiplier.SINGLE, band=band)


# --- DartInput band validation -------------------------------------------


def test_band_allowed_on_numbered_singles_only():
    assert banded(20, "outer").band == "outer"
    with pytest.raises(ValueError):
        DartInput(segment=20, multiplier=Multiplier.DOUBLE, band="outer")
    with pytest.raises(ValueError):
        DartInput(segment=25, multiplier=Multiplier.SINGLE, band="inner")
    with pytest.raises(ValueError):
        DartInput(segment=20, multiplier=Multiplier.SINGLE, band="middle")


def test_band_does_not_change_the_score():
    assert banded(20, "inner").score == 20


# --- Round sequence -------------------------------------------------------


def test_sequence_is_the_nine_house_rounds():
    assert [round_for_number(n) for n in range(1, 10)] == list(ROUND_SEQUENCE)


def test_rounds_past_nine_are_red_bull_tiebreaks():
    assert round_for_number(10) is HalveItRound.RED_BULL
    assert round_for_number(14) is HalveItRound.RED_BULL


# --- Band rounds ----------------------------------------------------------


def test_outer_black_scores_matching_darts_at_face_value():
    result = apply_halve_it_visit(
        0, 1, [banded(20, "outer"), banded(1, "outer"), miss()]
    )
    assert result.points_scored == 20  # the 1 is a white segment
    assert result.new_score == 20
    assert not result.was_halved


def test_wrong_band_halves():
    result = apply_halve_it_visit(
        45, 1, [banded(20, "inner"), banded(20, "inner"), banded(20, "inner")]
    )
    assert result.was_halved
    assert result.new_score == 23  # rounded up


def test_inner_white_round():
    result = apply_halve_it_visit(
        10, 4, [banded(19, "inner"), banded(5, "inner"), banded(18, "inner")]
    )
    assert result.points_scored == 24  # 19 + 5; the 18 is black
    assert result.new_score == 34


def test_bandless_singles_do_not_qualify_in_band_rounds():
    # A single without band information cannot prove where it landed.
    result = apply_halve_it_visit(20, 1, [single(20), single(18), single(13)])
    assert result.was_halved


def test_doubles_and_triples_do_not_qualify_in_band_rounds():
    result = apply_halve_it_visit(20, 1, [double(20), triple(20), miss()])
    assert result.was_halved


# --- Doubles / triples rounds --------------------------------------------


def test_doubles_round_scores_double_values():
    result = apply_halve_it_visit(0, 5, [double(16), single(20), double(5)])
    assert result.points_scored == 42
    assert result.new_score == 42


def test_inner_bull_is_not_part_of_the_double_ring():
    result = apply_halve_it_visit(30, 5, [inner_bull(), inner_bull(), inner_bull()])
    assert result.was_halved
    assert result.new_score == 15


def test_triples_round():
    result = apply_halve_it_visit(0, 6, [triple(20), triple(1), single(20)])
    assert result.points_scored == 63
    result_miss = apply_halve_it_visit(45, 6, [single(20), double(20), miss()])
    assert result_miss.was_halved
    assert result_miss.new_score == 23


# --- The 63 round ---------------------------------------------------------


def test_exact_sixty_three_awards_sixty_three():
    result = apply_halve_it_visit(100, 7, [triple(19), single(3), single(3)])
    assert result.points_scored == 63
    assert result.new_score == 163


def test_sixty_three_with_a_miss_still_counts_if_total_is_exact():
    result = apply_halve_it_visit(0, 7, [triple(20), single(3), miss()])
    assert result.points_scored == 63


def test_sixty_four_halves():
    result = apply_halve_it_visit(100, 7, [triple(20), single(2), single(2)])
    assert result.was_halved
    assert result.new_score == 50


# --- Bull rounds ----------------------------------------------------------


def test_green_bull_counts_outer_bulls_only():
    result = apply_halve_it_visit(0, 8, [outer_bull(), outer_bull(), inner_bull()])
    assert result.points_scored == 50  # two greens; the red does not count

    all_red = apply_halve_it_visit(45, 8, [inner_bull(), inner_bull(), inner_bull()])
    assert all_red.was_halved
    assert all_red.new_score == 23


def test_red_bull_counts_inner_bulls_only():
    result = apply_halve_it_visit(0, 9, [outer_bull(), outer_bull(), inner_bull()])
    assert result.points_scored == 50
    assert result.new_score == 50


# --- Halving edges --------------------------------------------------------


def test_halving_rounds_up_and_zero_stays_zero():
    assert halved(45) == 23
    assert halved(1) == 1
    assert halved(0) == 0


def test_round_requires_exactly_three_darts():
    with pytest.raises(ValueError):
        apply_halve_it_visit(0, 1, [banded(20, "outer")])
    with pytest.raises(ValueError):
        apply_halve_it_visit(0, 1, [miss()] * 4)
