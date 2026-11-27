"""Mouse controls for the desk, which handle notes the way hands do on the wall: press to peel
a note off (or take a fresh one), drag it, turn it with the wheel, let go to stick it down."""

import pytest

from lorikeet.desk.mouse import LEFT, RIGHT, TURN_STEP, DeskMouse
from lorikeet.desk.palette import Palette
from lorikeet.desk.source import DeskSceneSource, turned_square
from lorikeet.interface import PieceState, Point, Polygon, square

# On a 1000x600 canvas the palette bar's top edge is at y=500, so y<500 is open playfield.
PALETTE = Palette(("yellow", "pink"), canvas_size=(1000, 600))
PINK_SWATCH = PALETTE.swatches()[1][1]


@pytest.fixture
def desk() -> DeskSceneSource:
    return DeskSceneSource(note_size=100, clock=lambda: 0.0)  # time stands still


@pytest.fixture
def mouse(desk: DeskSceneSource) -> DeskMouse:
    return DeskMouse(desk, PALETTE)


def click(mouse: DeskMouse, pos: Point) -> None:
    mouse.press(pos, LEFT)
    mouse.release(pos, LEFT)


def drag(mouse: DeskMouse, start: Point, end: Point) -> None:
    mouse.press(start, LEFT)
    mouse.move(end)
    mouse.release(end, LEFT)


def outlines(desk: DeskSceneSource) -> list[Polygon]:
    return [piece.outline for piece in desk.latest().pieces]


def colors(desk: DeskSceneSource) -> list[str]:
    return [piece.color for piece in desk.latest().pieces]


def assert_same_shape(actual: Polygon, expected: Polygon) -> None:
    assert [pytest.approx(point) for point in actual] == list(expected)


def test_a_click_on_bare_surface_sticks_a_note_on_centred_there(
    desk: DeskSceneSource, mouse: DeskMouse
):
    click(mouse, (300, 200))

    assert outlines(desk) == [square((300, 200), 100)]


def test_notes_start_in_the_first_palette_colour(desk: DeskSceneSource, mouse: DeskMouse):
    click(mouse, (300, 200))

    assert colors(desk) == ["yellow"]


def test_a_note_held_in_the_hand_is_off_the_surface(desk: DeskSceneSource, mouse: DeskMouse):
    click(mouse, (300, 200))
    mouse.press((300, 200), LEFT)

    assert desk.latest().pieces == ()


def test_dragging_a_note_moves_it_to_where_you_let_go(desk: DeskSceneSource, mouse: DeskMouse):
    click(mouse, (300, 200))
    drag(mouse, (300, 200), (600, 300))

    assert outlines(desk) == [square((600, 300), 100)]


def test_a_moved_note_is_a_new_piece(desk: DeskSceneSource, mouse: DeskMouse):
    click(mouse, (300, 200))
    before = desk.latest().pieces[0].id
    drag(mouse, (300, 200), (600, 300))

    assert desk.latest().pieces[0].id != before


def test_a_note_stays_where_you_gripped_it(desk: DeskSceneSource, mouse: DeskMouse):
    click(mouse, (300, 200))
    drag(mouse, (320, 210), (620, 310))  # gripped 20 right and 10 below its centre

    assert outlines(desk) == [square((600, 300), 100)]


def test_a_moved_note_keeps_its_colour_and_turn(desk: DeskSceneSource, mouse: DeskMouse):
    desk.drop("pink", (300, 200), angle=30)
    drag(mouse, (300, 200), (600, 300))

    (piece,) = desk.latest().pieces
    assert piece.color == "pink"
    assert_same_shape(piece.outline, turned_square((600, 300), 100, 30))


def test_scrolling_turns_the_held_note(desk: DeskSceneSource, mouse: DeskMouse):
    mouse.press((300, 200), LEFT)
    mouse.scroll(3)
    mouse.release((300, 200), LEFT)

    assert_same_shape(outlines(desk)[0], turned_square((300, 200), 100, 3 * TURN_STEP))


def test_scrolling_with_nothing_held_does_nothing(desk: DeskSceneSource, mouse: DeskMouse):
    mouse.scroll(3)
    click(mouse, (300, 200))

    assert outlines(desk) == [square((300, 200), 100)]


def test_dragging_from_a_swatch_sticks_on_a_note_of_that_colour(
    desk: DeskSceneSource, mouse: DeskMouse
):
    drag(mouse, PINK_SWATCH, (300, 200))

    assert (colors(desk), outlines(desk)) == (["pink"], [square((300, 200), 100)])


def test_clicking_a_swatch_picks_that_colour_for_the_next_notes(
    desk: DeskSceneSource, mouse: DeskMouse
):
    click(mouse, PINK_SWATCH)
    click(mouse, (300, 200))

    assert colors(desk) == ["pink"]


def test_clicking_the_palette_bar_does_not_stick_a_note_on(desk: DeskSceneSource, mouse: DeskMouse):
    click(mouse, (PINK_SWATCH[0] - 50, PINK_SWATCH[1]))  # the gap between two swatches

    assert desk.latest().pieces == ()


def test_letting_go_over_the_palette_puts_the_note_back(desk: DeskSceneSource, mouse: DeskMouse):
    click(mouse, (300, 200))
    drag(mouse, (300, 200), PINK_SWATCH)

    assert desk.latest().pieces == ()


def test_with_the_palette_hidden_a_click_there_sticks_a_note_on(
    desk: DeskSceneSource, mouse: DeskMouse
):
    mouse.show_palette = False
    click(mouse, PINK_SWATCH)

    assert colors(desk) == ["yellow"]


def test_right_click_while_holding_puts_the_note_back(desk: DeskSceneSource, mouse: DeskMouse):
    click(mouse, (300, 200))
    mouse.press((300, 200), LEFT)
    mouse.press((300, 200), RIGHT)
    mouse.release((300, 200), LEFT)

    assert desk.latest().pieces == ()


def test_right_click_peels_off_the_note_under_the_cursor(desk: DeskSceneSource, mouse: DeskMouse):
    click(mouse, (300, 200))
    mouse.press((340, 230), RIGHT)

    assert desk.latest().pieces == ()


def test_right_click_on_the_bare_surface_does_nothing(desk: DeskSceneSource, mouse: DeskMouse):
    click(mouse, (300, 200))
    mouse.press((600, 200), RIGHT)

    assert len(desk.latest().pieces) == 1


def test_right_click_peels_the_top_note_where_two_overlap(desk: DeskSceneSource, mouse: DeskMouse):
    desk.drop("yellow", (300, 200))
    desk.drop("yellow", (350, 200))  # overlaps the first, and went on later, so it's on top
    mouse.press((325, 200), RIGHT)

    assert outlines(desk) == [square((300, 200), 100)]


def test_a_peeled_note_that_is_still_hidden_cannot_be_grabbed():
    now = [0.0]
    desk = DeskSceneSource(note_size=100, clock=lambda: now[0])
    mouse = DeskMouse(desk, PALETTE)
    desk.drop("pink", (300, 200))
    now[0] = 1.0  # settled, so peeling it leaves it HIDDEN for a while
    mouse.press((300, 200), RIGHT)

    click(mouse, (300, 200))  # nothing is really there any more, so this takes a fresh note

    assert [(p.color, p.state) for p in desk.latest().pieces] == [
        ("pink", PieceState.HIDDEN),
        ("yellow", PieceState.MOVING),
    ]


def test_other_buttons_do_nothing(desk: DeskSceneSource, mouse: DeskMouse):
    mouse.press((300, 200), 2)  # middle button
    mouse.release((300, 200), 2)

    assert desk.latest().pieces == ()
