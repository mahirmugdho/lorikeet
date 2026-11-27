"""Mouse controls for the sim: pick a colour from the palette, left-click sticks a note on,
right-click peels one off."""

import pytest

from lorikeet.interface import PieceState, square
from lorikeet.sim.mouse import LEFT, RIGHT, SimMouse
from lorikeet.sim.palette import Palette
from lorikeet.sim.source import SimSceneSource

# On a 1000x600 canvas the palette bar's top edge is at y=500, so y=200 is open playfield.
PALETTE = Palette(("yellow", "pink"), canvas_size=(1000, 600))
PINK_SWATCH = PALETTE.swatches()[1][1]


@pytest.fixture
def sim() -> SimSceneSource:
    return SimSceneSource(note_size=100, clock=lambda: 0.0)  # time stands still


@pytest.fixture
def mouse(sim: SimSceneSource) -> SimMouse:
    return SimMouse(sim, PALETTE)


def colors(sim: SimSceneSource) -> list[str]:
    return [piece.color for piece in sim.latest().pieces]


def test_left_click_sticks_a_note_on_centred_at_the_cursor(sim: SimSceneSource, mouse: SimMouse):
    mouse.click((300, 200), LEFT)

    (piece,) = sim.latest().pieces
    assert piece.outline == square((300, 200), 100)


def test_notes_start_in_the_first_palette_colour(sim: SimSceneSource, mouse: SimMouse):
    mouse.click((300, 200), LEFT)

    assert colors(sim) == ["yellow"]


def test_clicking_a_swatch_picks_that_colour_for_the_next_notes(
    sim: SimSceneSource, mouse: SimMouse
):
    mouse.click(PINK_SWATCH, LEFT)
    mouse.click((300, 200), LEFT)

    assert colors(sim) == ["pink"]


def test_clicking_the_palette_bar_does_not_stick_a_note_on(sim: SimSceneSource, mouse: SimMouse):
    mouse.click((PINK_SWATCH[0] - 50, PINK_SWATCH[1]), LEFT)  # the gap between two swatches

    assert sim.latest().pieces == ()


def test_with_the_palette_hidden_a_click_there_sticks_a_note_on(
    sim: SimSceneSource, mouse: SimMouse
):
    mouse.show_palette = False
    mouse.click(PINK_SWATCH, LEFT)

    assert colors(sim) == ["yellow"]


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
    mouse = SimMouse(sim, PALETTE)
    mouse.click((300, 200), LEFT)
    now[0] = 1.0  # settled, so peeling it leaves it HIDDEN for a while
    mouse.click((300, 200), RIGHT)

    mouse.click((300, 200), RIGHT)  # nothing is really there any more, so this must not fail

    assert [piece.state for piece in sim.latest().pieces] == [PieceState.HIDDEN]


def test_other_buttons_do_nothing(sim: SimSceneSource, mouse: SimMouse):
    mouse.click((300, 200), 2)  # middle button
    mouse.click((300, 200), 4)  # scroll wheel

    assert sim.latest().pieces == ()
