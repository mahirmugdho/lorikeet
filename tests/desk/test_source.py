"""Desk notes follow the same rules as real ones through the camera pipeline (ADR 0004)."""

import pytest

from lorikeet.desk.source import DeskSceneSource
from lorikeet.interface import PieceState, square


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
def desk(clock: Clock) -> DeskSceneSource:
    return DeskSceneSource(note_size=100, settle_seconds=0.2, hidden_seconds=2.0, clock=clock)


def test_starts_with_nothing_on_the_surface(desk: DeskSceneSource):
    assert desk.latest().pieces == ()


def test_scene_time_comes_from_the_clock(desk: DeskSceneSource, clock: Clock):
    clock.now = 3.5

    assert desk.latest().time == 3.5


def test_a_dropped_note_is_a_square_of_its_colour(desk: DeskSceneSource):
    desk.drop("yellow", (300, 200))

    (piece,) = desk.latest().pieces
    assert (piece.color, piece.outline) == ("yellow", square((300, 200), 100))


def test_a_note_is_one_convex_part(desk: DeskSceneSource):
    desk.drop("pink", (300, 200), angle=30)

    (piece,) = desk.latest().pieces
    assert piece.parts == (piece.outline,)


def test_drop_returns_the_id_the_piece_has_in_the_scene(desk: DeskSceneSource):
    note = desk.drop("yellow", (100, 100))

    assert [piece.id for piece in desk.latest().pieces] == [note]


def test_scene_lists_every_note_on_the_surface(desk: DeskSceneSource):
    first = desk.drop("yellow", (100, 100))
    second = desk.drop("blue", (400, 100))

    assert [piece.id for piece in desk.latest().pieces] == [first, second]


def test_a_positive_angle_turns_the_note_clockwise_on_screen(desk: DeskSceneSource):
    desk.drop("pink", (0, 0), angle=90)

    # y grows downward, so a quarter turn clockwise takes the top-left corner to the top right.
    top_left = desk.latest().pieces[0].outline[0]
    assert top_left == pytest.approx((50, -50))


def test_a_note_turns_about_its_centre(desk: DeskSceneSource):
    desk.drop("pink", (300, 200), angle=30)

    assert desk.latest().pieces[0].center == pytest.approx((300, 200))


def test_a_new_note_is_moving_until_the_settle_time_passes(desk: DeskSceneSource, clock: Clock):
    desk.drop("yellow", (100, 100))
    clock.now = 0.19

    assert desk.latest().pieces[0].state is PieceState.MOVING


def test_a_note_still_for_the_settle_time_is_settled(desk: DeskSceneSource, clock: Clock):
    desk.drop("yellow", (100, 100))
    clock.now = 0.2

    assert desk.latest().pieces[0].state is PieceState.SETTLED


def test_picking_up_a_moving_note_removes_it_at_once(desk: DeskSceneSource, clock: Clock):
    note = desk.drop("yellow", (100, 100))
    clock.now = 0.1
    desk.pick_up(note)

    assert desk.latest().pieces == ()


def test_a_picked_up_settled_note_stays_hidden_for_the_grace_period(
    desk: DeskSceneSource, clock: Clock
):
    note = desk.drop("yellow", (100, 100))
    clock.now = 1.0
    desk.pick_up(note)
    clock.now = 2.9

    assert [piece.state for piece in desk.latest().pieces] == [PieceState.HIDDEN]


def test_a_hidden_note_is_gone_once_the_grace_period_ends(desk: DeskSceneSource, clock: Clock):
    note = desk.drop("yellow", (100, 100))
    clock.now = 1.0
    desk.pick_up(note)
    clock.now = 3.0

    assert desk.latest().pieces == ()


def test_putting_a_note_back_down_makes_a_new_piece(desk: DeskSceneSource):
    first = desk.drop("yellow", (100, 100))
    desk.pick_up(first)
    second = desk.drop("yellow", (100, 100))

    assert second != first


def test_cannot_pick_up_a_note_that_is_already_off_the_surface(desk: DeskSceneSource, clock: Clock):
    note = desk.drop("yellow", (100, 100))
    clock.now = 1.0
    desk.pick_up(note)

    with pytest.raises(KeyError):
        desk.pick_up(note)


def test_note_size_must_be_positive(clock: Clock):
    with pytest.raises(ValueError, match="note_size"):
        DeskSceneSource(note_size=0, clock=clock)
