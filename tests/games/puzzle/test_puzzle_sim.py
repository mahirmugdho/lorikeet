"""Game rules on scripted scenes: Sun springs, two-touch paper, determinism, levels beatable."""

import pytest

from lorikeet.games.puzzle.level import LEVELS_DIR, PAD_TOP, Level, Rect, load_level
from lorikeet.games.puzzle.sim import (
    EGG_RADIUS,
    SPRING_GAIN,
    SPRING_MAX,
    SPRING_MIN,
    Event,
    Outcome,
    PlacedNote,
    Run,
)

LEVEL_IDS = sorted(p.stem for p in LEVELS_DIR.glob("*.json"))


def drop_test(egg_y: int, note: PlacedNote, floor: bool = False) -> Level:
    """The egg dropped straight down onto one note, the blossom far out of reach."""
    terrain = (Rect(0, 140, 320, 10),) if floor else ()  # a shelf above the splat floor
    return Level(
        id="test",
        name="test",
        nest=(note.x, egg_y),
        nudge=(0.0, 0.0),
        blossom=(10, 10),
        terrain=terrain,
        pad=(("sun", 1),),
        par=1,
    )


def first_spring(run: Run) -> Event:
    for _ in range(2000):
        run.step()
        springs = [e for e in run.drain_events() if e.kind == "spring"]
        if springs:
            return springs[0]
    raise AssertionError("the egg never touched the note")


def test_harder_landing_springs_higher() -> None:
    note = PlacedNote("sun", 160, 120)
    low, high = Run(drop_test(100, note), [note]), Run(drop_test(20, note), [note])
    soft, hard = first_spring(low), first_spring(high)
    assert hard.speed > soft.speed
    assert -high.egg.velocity.y > -low.egg.velocity.y > 0  # both go up, the hard one faster


def test_spring_leaves_along_the_face_normal() -> None:
    note = PlacedNote("sun", 160, 120, 30)
    run = Run(drop_test(40, note), [note])
    ev = first_spring(run)
    n = note.up_normal()
    expected = min(SPRING_MAX, max(SPRING_MIN, SPRING_GAIN * ev.speed))
    assert run.egg.velocity.dot(n) == pytest.approx(expected)


def test_note_peels_after_its_second_touch() -> None:
    note = PlacedNote("sun", 160, 120)
    run = Run(drop_test(60, note), [note])
    first_spring(run)
    assert run.notes[0].touches == 1
    assert not run.notes[0].peeled
    run.run_to_end()
    assert run.notes[0].touches == 2
    assert run.notes[0].peeled
    assert run.outcome is Outcome.SPLAT  # with the note gone, it drops to the floor


def test_same_layout_plays_out_identically() -> None:
    level = load_level("1-1")
    notes = [PlacedNote(*n) for n in level.solution]
    a, b = Run(level, notes), Run(level, notes)
    for _ in range(200):
        a.step()
        b.step()
    assert a.snapshot() == b.snapshot()
    a.run_to_end()
    b.run_to_end()
    assert a.snapshot() == b.snapshot()


@pytest.mark.parametrize("level_id", LEVEL_IDS)
def test_known_solution_wins(level_id: str) -> None:
    level = load_level(level_id)
    assert level.solution, f"{level_id} needs a known solution"
    assert len(level.solution) <= level.par
    assert Run(level, [PlacedNote(*n) for n in level.solution]).run_to_end() is Outcome.WON


@pytest.mark.parametrize("level_id", LEVEL_IDS)
def test_no_notes_does_not_win(level_id: str) -> None:
    assert Run(load_level(level_id), []).run_to_end() is not Outcome.WON


def test_a_missed_egg_splats_on_the_floor() -> None:
    run = Run(load_level("1-1"), [])
    assert run.run_to_end() is Outcome.SPLAT
    assert run.egg.position.y + EGG_RADIUS >= PAD_TOP


def test_resting_egg_stalls_after_the_timeout() -> None:
    note = PlacedNote("sun", 160, 60)
    level = drop_test(130, note, floor=True)  # it starts on the shelf, the note far above
    run = Run(level, [])
    assert run.run_to_end() is Outcome.STALLED
    assert run.step_count == pytest.approx(level.timeout_s * 120, abs=2)
