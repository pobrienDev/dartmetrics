"""Unit tests for the Cricket engine — mirrors the acceptance table in
docs/GAME_MODES.md."""

import pytest

from app.scoring.cricket import (
    CRICKET_TARGETS,
    apply_cricket_dart,
    initial_marks,
    is_board_closed,
)
from app.scoring.domain import double, inner_bull, miss, outer_bull, single, triple


def board(**overrides: int) -> dict[int, int]:
    """Marks state with named overrides, e.g. board(t20=2, bull=1)."""
    marks = initial_marks()
    for key, value in overrides.items():
        target = 25 if key == "bull" else int(key.lstrip("t"))
        marks[target] = value
    return marks


def test_initial_board_is_open_everywhere():
    marks = initial_marks()
    assert set(marks) == set(CRICKET_TARGETS)
    assert all(v == 0 for v in marks.values())
    assert not is_board_closed(marks)


def test_triple_closes_an_open_target_from_zero():
    result = apply_cricket_dart(board(), triple(20))
    assert result.marks[20] == 3
    assert result.target_hit == 20
    assert result.marks_added == 3
    assert not result.leg_won


def test_overflow_marks_are_discarded():
    result = apply_cricket_dart(board(t20=2), triple(20))
    assert result.marks[20] == 3  # not 5
    assert result.marks_added == 1


def test_single_and_double_add_their_marks():
    assert apply_cricket_dart(board(), single(19)).marks[19] == 1
    assert apply_cricket_dart(board(), double(18)).marks[18] == 2


def test_hits_on_a_closed_target_do_nothing():
    result = apply_cricket_dart(board(t20=3), triple(20))
    assert result.marks[20] == 3
    assert result.target_hit is None
    assert result.marks_added == 0


@pytest.mark.parametrize("dart", [single(14), triple(7), double(1), miss()])
def test_non_targets_do_nothing(dart):
    result = apply_cricket_dart(board(), dart)
    assert result.marks == board()
    assert result.target_hit is None
    assert result.marks_added == 0


def test_outer_bull_is_one_mark_inner_is_two():
    assert apply_cricket_dart(board(), outer_bull()).marks[25] == 1
    assert apply_cricket_dart(board(), inner_bull()).marks[25] == 2


def test_inner_bull_from_two_marks_closes_with_overflow_discarded():
    result = apply_cricket_dart(board(bull=2), inner_bull())
    assert result.marks[25] == 3
    assert result.marks_added == 1


def all_closed_except(target: int, marks_on_target: int) -> dict[int, int]:
    marks = {t: 3 for t in CRICKET_TARGETS}
    marks[target] = marks_on_target
    return marks


def test_closing_the_last_target_wins_the_leg():
    result = apply_cricket_dart(all_closed_except(25, 2), outer_bull())
    assert result.leg_won
    assert result.turn_should_end
    assert is_board_closed(result.marks)


def test_closing_a_target_does_not_win_while_others_are_open():
    result = apply_cricket_dart(board(t15=2), single(15))
    assert result.marks[15] == 3
    assert not result.leg_won
    assert not result.turn_should_end


def test_input_state_is_never_mutated():
    original = board(t20=1)
    snapshot = dict(original)
    apply_cricket_dart(original, triple(20))
    assert original == snapshot
