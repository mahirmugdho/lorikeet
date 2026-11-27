"""Mouse controls for the sim: left-click sticks a note on, right-click peels one off."""

import pytest

from lorikeet.interface import PieceState, square
from lorikeet.sim.mouse import LEFT, RIGHT, SimMouse
from lorikeet.sim.source import SimSceneSource


@pytest.fixture
def sim() -> SimSceneSource:
    return SimSceneSource(note_size=100, clock=lambda: 0.0)  # time stands still


@pytest.fixture
def mouse(sim: SimSceneSource) -> SimMouse:
    return SimMouse(sim, color="yellow")


def test_left_click_sticks_a_note_on_centred_at_the_cursor(sim: SimSceneSource, mouse: SimMouse):
    mouse.click((300, 200), LEFT)

    (piece,) = sim.latest().pieces
    assert (piece.color, piece.outline) == ("yellow", square((300, 200), 100))


def test_right_click_peels_off_the_note_under_the_cursor(sim: SimSceneSource, mouse: SimMouse):
    mouse.click((300, 200), LEFT)
    mouse.click((340, 230), RIGHT)

    assert sim.latest().pieces == ()


def test_right_click_on_the_bare_surface_does_nothing(sim: SimSceneSource, mouse: SimMouse):
    mouse.click((300, 200), LEFT)
    mouse.click((600, 200), RIGHT)

    assert len(sim.latest().pieces) == 1


def test_right_click_peels_the_top_note_where_two_overlap(sim: SimSceneSource, mouse: SimMouse):
    mouse.click((300, 200), LEFT)
    mouse.click((350, 200), LEFT)  # overlaps the first, and went on later, so it's on top
    mouse.click((325, 200), RIGHT)

    assert [piece.outline for piece in sim.latest().pieces] == [square((300, 200), 100)]


def test_a_peeled_note_that_is_still_hidden_cannot_be_peeled_again():
    now = [0.0]
    sim = SimSceneSource(note_size=100, clock=lambda: now[0])
    mouse = SimMouse(sim, color="yellow")
    mouse.click((300, 200), LEFT)
    now[0] = 1.0  # settled, so peeling it leaves it HIDDEN for a while
    mouse.click((300, 200), RIGHT)

    mouse.click((300, 200), RIGHT)  # nothing is really there any more, so this must not fail

    assert [piece.state for piece in sim.latest().pieces] == [PieceState.HIDDEN]


def test_other_buttons_do_nothing(sim: SimSceneSource, mouse: SimMouse):
    mouse.click((300, 200), 2)  # middle button
    mouse.click((300, 200), 4)  # scroll wheel

    assert sim.latest().pieces == ()
