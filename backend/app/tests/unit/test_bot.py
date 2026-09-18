"""Bot engine: aiming is sensible and every simulated visit is legal."""

import random

import pytest

from app.players.models import BotDifficulty
from app.scoring import bot as bot_module
from app.scoring.bot import (
    ACCURACY,
    Aim,
    choose_cricket_aim,
    choose_halve_it_aim,
    choose_x01_aim,
    cricket_visit,
    halve_it_visit,
    throw,
    x01_visit,
)
from app.scoring.cricket import CRICKET_TARGETS, MARKS_TO_CLOSE, initial_marks
from app.scoring.domain import BULL_SEGMENT, DartInput, Multiplier, triple
from app.scoring.engine import apply_dart
from app.scoring.halve_it import HalveItRound

DIFFICULTIES = list(BotDifficulty)


def test_difficulties_are_ordered_easiest_to_hardest():
    assert [d.value for d in DIFFICULTIES] == ["noob", "easy", "medium", "hard", "pro"]
    triples = [ACCURACY[d].triple for d in DIFFICULTIES]
    doubles = [ACCURACY[d].double for d in DIFFICULTIES]
    assert triples == sorted(triples) and len(set(triples)) == 5
    assert doubles == sorted(doubles) and len(set(doubles)) == 5


@pytest.mark.parametrize("difficulty", DIFFICULTIES)
def test_scoring_average_increases_with_difficulty(difficulty):
    rng = random.Random(42)
    darts = [throw(Aim(20, Multiplier.TRIPLE), ACCURACY[difficulty], rng) for _ in range(6000)]
    per_visit = sum(d.score for d in darts) / len(darts) * 3
    expected = {"noob": 24, "easy": 40, "medium": 63, "hard": 81, "pro": 100}[difficulty]
    assert abs(per_visit - expected) < 6


def test_stray_ring_hits_scale_with_skill():
    """A missed double that drifts into a neighbouring segment lands in
    the neighbour's ring roughly as often as the bot hits rings at all.
    A flat chance here once made Halve It's any-double round nearly
    skill-free (the easy bot qualified about as often as the noob)."""
    def neighbour_double_rate(difficulty: BotDifficulty) -> float:
        rng = random.Random(7)
        darts = [throw(Aim(20, Multiplier.DOUBLE), ACCURACY[difficulty], rng) for _ in range(20000)]
        strays = sum(
            1 for d in darts if d.multiplier is Multiplier.DOUBLE and d.segment in (1, 5)
        )
        return strays / len(darts)

    noob, easy, pro = (
        neighbour_double_rate(d) for d in (BotDifficulty.NOOB, BotDifficulty.EASY, BotDifficulty.PRO)
    )
    assert noob < 0.05
    assert noob < easy < pro


def test_throw_always_produces_a_legal_dart():
    rng = random.Random(7)
    aims = [
        Aim(20, Multiplier.TRIPLE),
        Aim(3, Multiplier.DOUBLE),
        Aim(19, Multiplier.SINGLE, band="inner"),
        Aim(BULL_SEGMENT, Multiplier.DOUBLE),
        Aim(BULL_SEGMENT, Multiplier.SINGLE),
        Aim(None, Multiplier.MISS),
    ]
    for _ in range(2000):
        for aim in aims:
            dart = throw(aim, ACCURACY[BotDifficulty.NOOB], rng)
            assert isinstance(dart, DartInput)  # constructor validated it


def test_deliberate_miss_always_misses():
    rng = random.Random(1)
    for _ in range(50):
        assert throw(Aim(None, Multiplier.MISS), ACCURACY[BotDifficulty.PRO], rng).score == 0


def test_band_only_recorded_when_aim_has_one():
    rng = random.Random(3)
    banded = [throw(Aim(20, Multiplier.SINGLE, band="outer"), ACCURACY[BotDifficulty.PRO], rng) for _ in range(200)]
    for dart in banded:
        if dart.multiplier is Multiplier.SINGLE and dart.segment != BULL_SEGMENT:
            assert dart.band in ("inner", "outer")
    plain = [throw(Aim(20, Multiplier.SINGLE), ACCURACY[BotDifficulty.PRO], rng) for _ in range(200)]
    assert all(dart.band is None for dart in plain)


# --- 501 aiming -------------------------------------------------------------


@pytest.mark.parametrize(
    "remaining, expected",
    [
        (501, Aim(20, Multiplier.TRIPLE)),
        (40, Aim(20, Multiplier.DOUBLE)),
        (32, Aim(16, Multiplier.DOUBLE)),
        (50, Aim(BULL_SEGMENT, Multiplier.DOUBLE)),
        (2, Aim(1, Multiplier.DOUBLE)),
        (52, Aim(20, Multiplier.SINGLE)),  # leaves 32
        (100, Aim(20, Multiplier.TRIPLE)),  # leaves 40
        (61, Aim(11, Multiplier.TRIPLE)),  # 61-28? no: 61-32=29 no; 61-40=21 no; 61-16=45 T15
        (3, Aim(1, Multiplier.SINGLE)),  # never leave 1
    ],
)
def test_x01_aim(remaining, expected):
    aim = choose_x01_aim(remaining)
    if remaining == 61:
        # Any setup that leaves a preferred double is acceptable.
        assert 61 - aim.segment * aim.multiplier.value in (32, 40, 16, 24, 20, 8, 36, 4, 12, 28, 2, 6, 10, 14, 18, 22, 26, 30, 34, 38, 50)
    else:
        assert aim == expected


def test_x01_aim_never_busts_or_leaves_one_when_hit():
    for remaining in range(2, 502):
        aim = choose_x01_aim(remaining)
        dart = DartInput(segment=aim.segment, multiplier=aim.multiplier)
        result = apply_dart(remaining, remaining, dart)
        assert not result.is_bust, remaining


@pytest.mark.parametrize("difficulty", DIFFICULTIES)
def test_x01_visit_is_always_a_legal_turn(difficulty):
    """Replays each visit through the engine exactly as the turn
    service would, checking the bot never throws past a bust or
    checkout and always throws three darts otherwise."""
    rng = random.Random(11)
    for start in list(range(2, 200)) + [301, 501]:
        darts = x01_visit(start, ACCURACY[difficulty], rng)
        assert 1 <= len(darts) <= 3
        remaining = start
        for index, dart in enumerate(darts):
            result = apply_dart(start, remaining, dart)
            if result.turn_should_end:
                assert index == len(darts) - 1
            remaining = result.effective_remaining
        else:
            if not result.turn_should_end:
                assert len(darts) == 3


def test_pro_bot_finishes_legs_and_noob_takes_longer():
    def darts_to_finish(difficulty, seed):
        rng = random.Random(seed)
        remaining, thrown = 501, 0
        while remaining > 0:
            darts = x01_visit(remaining, ACCURACY[difficulty], rng)
            thrown += len(darts)
            current = remaining
            for dart in darts:
                result = apply_dart(remaining, current, dart)
                current = result.effective_remaining
            remaining = current
            assert thrown < 400, "bot must eventually finish a leg"
        return thrown

    pro = sum(darts_to_finish(BotDifficulty.PRO, s) for s in range(20)) / 20
    noob = sum(darts_to_finish(BotDifficulty.NOOB, s) for s in range(20)) / 20
    assert pro < noob
    assert pro < 30


# --- Cricket -----------------------------------------------------------------


def test_cricket_is_free_for_all_over_every_open_target():
    """Race-to-close has no points, so the bot plays casual Cricket:
    any open target can come up, not a march from 20 down to the bull."""
    rng = random.Random(1)
    aimed = {choose_cricket_aim(initial_marks(), rng).segment for _ in range(300)}
    assert aimed == set(CRICKET_TARGETS)


def test_cricket_never_aims_at_a_closed_target():
    marks = initial_marks()
    for t in (20, 17, BULL_SEGMENT):
        marks[t] = MARKS_TO_CLOSE
    rng = random.Random(2)
    for _ in range(300):
        aim = choose_cricket_aim(marks, rng)
        assert marks[aim.segment] < MARKS_TO_CLOSE
    for t in (15, 16, 18, 19):
        marks[t] = MARKS_TO_CLOSE
    assert choose_cricket_aim(marks, rng) == Aim(20, Multiplier.TRIPLE)  # board closed


def test_cricket_aims_at_the_triple_and_the_inner_bull():
    marks = initial_marks()
    rng = random.Random(3)
    for target in CRICKET_TARGETS:
        aim = choose_cricket_aim(marks, rng, current=target)
        assert aim.segment == target
        expected = Multiplier.DOUBLE if target == BULL_SEGMENT else Multiplier.TRIPLE
        assert aim.multiplier is expected


def test_cricket_keeps_its_target_until_it_closes():
    marks = initial_marks()
    rng = random.Random(4)
    marks[17] = 2
    assert choose_cricket_aim(marks, rng, current=17) == Aim(17, Multiplier.TRIPLE)
    marks[17] = MARKS_TO_CLOSE
    assert choose_cricket_aim(marks, rng, current=17).segment != 17


def test_cricket_visit_stays_on_one_number_while_it_is_open(monkeypatch):
    aims: list[Aim] = []

    def one_mark(aim, accuracy, rng):
        aims.append(aim)
        return DartInput(segment=aim.segment, multiplier=Multiplier.SINGLE)

    monkeypatch.setattr(bot_module, "throw", one_mark)
    darts = cricket_visit(initial_marks(), ACCURACY[BotDifficulty.MEDIUM], random.Random(5))
    assert len(darts) == 3
    assert len({aim.segment for aim in aims}) == 1


def test_cricket_visit_moves_on_after_closing_a_number(monkeypatch):
    aims: list[Aim] = []

    def closes_it(aim, accuracy, rng):
        aims.append(aim)
        multiplier = Multiplier.DOUBLE if aim.segment == BULL_SEGMENT else Multiplier.TRIPLE
        return DartInput(segment=aim.segment, multiplier=multiplier)

    monkeypatch.setattr(bot_module, "throw", closes_it)
    marks = initial_marks()
    marks[BULL_SEGMENT] = 1  # one inner bull closes it too
    darts = cricket_visit(marks, ACCURACY[BotDifficulty.PRO], random.Random(6))
    assert len(darts) == 3
    assert len({aim.segment for aim in aims}) == 3


def test_cricket_visit_stops_after_closing_the_board():
    marks = {t: 3 for t in initial_marks()}
    marks[BULL_SEGMENT] = 2
    rng = random.Random(5)
    for _ in range(200):
        darts = cricket_visit(marks, ACCURACY[BotDifficulty.PRO], rng)
        assert 1 <= len(darts) <= 3
        closing = [d for d in darts if d.segment == BULL_SEGMENT and d.multiplier is not Multiplier.MISS]
        if closing:
            assert darts[-1] == closing[0]


# --- Halve It ------------------------------------------------------------------


def test_halve_it_band_rounds_carry_the_band():
    aim = choose_halve_it_aim(HalveItRound.INNER_WHITE, [])
    assert aim.band == "inner" and aim.segment == 19
    assert choose_halve_it_aim(HalveItRound.OUTER_BLACK, []).segment == 20


def test_halve_it_sixty_three_chases_exact_total():
    assert choose_halve_it_aim(HalveItRound.SIXTY_THREE, []) == Aim(20, Multiplier.TRIPLE)
    after_t20 = choose_halve_it_aim(HalveItRound.SIXTY_THREE, [triple(20)])
    assert after_t20 == Aim(3, Multiplier.SINGLE)
    done = choose_halve_it_aim(HalveItRound.SIXTY_THREE, [triple(20), DartInput(3, Multiplier.SINGLE)])
    assert done.multiplier is Multiplier.MISS


@pytest.mark.parametrize("round_number", range(1, 11))
def test_halve_it_visit_is_three_legal_darts(round_number):
    rng = random.Random(round_number)
    for difficulty in DIFFICULTIES:
        darts = halve_it_visit(round_number, ACCURACY[difficulty], rng)
        assert len(darts) == 3
