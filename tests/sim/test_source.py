"""Simulated notes follow the same rules as real ones through the camera pipeline (ADR 0004)."""

import pytest

from lorikeet.interface import PieceState, square
from lorikeet.sim.source import SimSceneSource


class Clock:
    """A clock the test moves by hand, so every timing is exact."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def sim(clock: Clock) -> SimSceneSource:
    return SimSceneSource(note_size=100, settle_seconds=0.2, hidden_seconds=2.0, clock=clock)


def test_starts_with_nothing_on_the_surface(sim: SimSceneSource):
    assert sim.latest().pieces == ()


def test_scene_time_comes_from_the_clock(sim: SimSceneSource, clock: Clock):
    clock.now = 3.5

    assert sim.latest().time == 3.5


def test_a_dropped_note_is_a_square_of_its_colour(sim: SimSceneSource):
    sim.drop("yellow", (300, 200))

    (piece,) = sim.latest().pieces
    assert (piece.color, piece.outline) == ("yellow", square((300, 200), 100))


def test_a_note_is_one_convex_part(sim: SimSceneSource):
    sim.drop("pink", (300, 200), angle=30)

    (piece,) = sim.latest().pieces
    assert piece.parts == (piece.outline,)


def test_drop_returns_the_id_the_piece_has_in_the_scene(sim: SimSceneSource):
    note = sim.drop("yellow", (100, 100))

    assert [piece.id for piece in sim.latest().pieces] == [note]


def test_scene_lists_every_note_on_the_surface(sim: SimSceneSource):
    first = sim.drop("yellow", (100, 100))
    second = sim.drop("blue", (400, 100))

    assert [piece.id for piece in sim.latest().pieces] == [first, second]


def test_a_positive_angle_turns_the_note_clockwise_on_screen(sim: SimSceneSource):
    sim.drop("pink", (0, 0), angle=90)

    # y grows downward, so a quarter turn clockwise takes the top-left corner to the top right.
    top_left = sim.latest().pieces[0].outline[0]
    assert top_left == pytest.approx((50, -50))


def test_a_note_turns_about_its_centre(sim: SimSceneSource):
    sim.drop("pink", (300, 200), angle=30)

    assert sim.latest().pieces[0].center == pytest.approx((300, 200))


def test_a_new_note_is_moving_until_the_settle_time_passes(sim: SimSceneSource, clock: Clock):
    sim.drop("yellow", (100, 100))
    clock.now = 0.19

    assert sim.latest().pieces[0].state is PieceState.MOVING


def test_a_note_still_for_the_settle_time_is_settled(sim: SimSceneSource, clock: Clock):
    sim.drop("yellow", (100, 100))
    clock.now = 0.2

    assert sim.latest().pieces[0].state is PieceState.SETTLED


def test_picking_up_a_moving_note_removes_it_at_once(sim: SimSceneSource, clock: Clock):
    note = sim.drop("yellow", (100, 100))
    clock.now = 0.1
    sim.pick_up(note)

    assert sim.latest().pieces == ()


def test_a_picked_up_settled_note_stays_hidden_for_the_grace_period(
    sim: SimSceneSource, clock: Clock
):
    note = sim.drop("yellow", (100, 100))
    clock.now = 1.0
    sim.pick_up(note)
    clock.now = 2.9

    assert [piece.state for piece in sim.latest().pieces] == [PieceState.HIDDEN]


def test_a_hidden_note_is_gone_once_the_grace_period_ends(sim: SimSceneSource, clock: Clock):
    note = sim.drop("yellow", (100, 100))
    clock.now = 1.0
    sim.pick_up(note)
    clock.now = 3.0

    assert sim.latest().pieces == ()


def test_putting_a_note_back_down_makes_a_new_piece(sim: SimSceneSource):
    first = sim.drop("yellow", (100, 100))
    sim.pick_up(first)
    second = sim.drop("yellow", (100, 100))

    assert second != first


def test_cannot_pick_up_a_note_that_is_already_off_the_surface(sim: SimSceneSource, clock: Clock):
    note = sim.drop("yellow", (100, 100))
    clock.now = 1.0
    sim.pick_up(note)

    with pytest.raises(KeyError):
        sim.pick_up(note)


def test_note_size_must_be_positive(clock: Clock):
    with pytest.raises(ValueError, match="note_size"):
        SimSceneSource(note_size=0, clock=clock)
