"""The sketch renderer draws a game's View in pencil on paper, boiling like the desk's notes."""

from collections.abc import Iterator

import pygame
import pytest

from lorikeet.render.sketch import PAPER, SketchLooks, SketchRenderer
from lorikeet.view import Circle, Outline, Text, Thing, View

SIZE = (320, 180)
LEDGE = Outline(((-60, -30), (60, -30), (60, 30), (-60, 30)))  # at (160, 90): 100..220, 60..120


def sketched(*things: Thing, at: float = 0.0) -> pygame.Surface:
    """`things` drawn on paper by sketch looks whose clock reads `at`."""
    canvas = pygame.Surface(SIZE)
    canvas.fill(PAPER)
    looks = SketchLooks(clock=lambda: at)
    for thing in View(things=things).back_to_front():
        looks.draw(canvas, thing)
    return canvas


def pixel(canvas: pygame.Surface, x: int, y: int) -> tuple[int, int, int]:
    r, g, b, _ = canvas.get_at((x, y))
    return (r, g, b)


def darkest(canvas: pygame.Surface, area: pygame.Rect) -> int:
    return min(
        min(pixel(canvas, x, y))
        for x in range(area.left, area.right)
        for y in range(area.top, area.bottom)
    )


def ledge() -> Thing:
    return Thing(id=1, kind="terrain", shape=LEDGE, position=(160, 90))


def test_terrain_is_washed_in_and_outlined_in_pencil():
    canvas = sketched(ledge())

    assert pixel(canvas, 160, 90) != PAPER  # washed in
    assert darkest(canvas, pygame.Rect(150, 54, 20, 12)) < 120  # a pencil line along its top


def test_the_lines_hold_still_within_a_boil_frame():
    first = pygame.image.tobytes(sketched(ledge(), at=0.0), "RGB")

    assert pygame.image.tobytes(sketched(ledge(), at=0.05), "RGB") == first


def test_the_lines_are_redrawn_on_the_next_boil_frame():
    first = pygame.image.tobytes(sketched(ledge(), at=0.0), "RGB")

    assert pygame.image.tobytes(sketched(ledge(), at=0.1), "RGB") != first


def test_a_note_is_outlined_just_outside_its_edge_and_its_paper_left_alone():
    note = Thing(id=1, kind="note", shape=LEDGE, position=(160, 90))  # 100..220, 60..120

    canvas = sketched(note)

    assert darkest(canvas, pygame.Rect(130, 48, 60, 12)) < 120
    assert pygame.transform.average_color(canvas, pygame.Rect(108, 68, 104, 44))[:3] == PAPER


def test_the_go_spot_leaves_its_middle_empty_for_the_note_on_it():
    go = Thing(id=1, kind="go", shape=Circle(40), position=(160, 90), pose="on")

    assert pixel(sketched(go), 160, 90) == PAPER


def test_words_are_written_where_they_are():
    words = Thing(id=1, kind="message", shape=Text("Hello", size=40), position=(160, 90))

    canvas = sketched(words)

    assert pygame.transform.average_color(canvas, pygame.Rect(100, 70, 120, 40))[:3] != PAPER


def test_a_kind_without_a_look_is_still_sketched():
    thing = Thing(id=1, kind="mystery", shape=Circle(20), position=(160, 90))

    assert darkest(sketched(thing), pygame.Rect(130, 60, 60, 60)) < 120


# The headless driver has no GPU renderer, so SCALED falls back to a slower one and says so.
@pytest.mark.filterwarnings("ignore:no fast renderer available")
def test_the_renderer_draws_on_paper(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    pygame.init()
    try:
        renderer = SketchRenderer("window", SIZE, display=0)
        bare_wall = pygame.Surface(SIZE)
        bare_wall.fill((255, 255, 255))
        renderer.draw(View(), bare_wall, pygame.Surface(SIZE, pygame.SRCALPHA))
        screen = pygame.display.get_surface()
        assert screen is not None
        assert pygame.transform.average_color(screen)[:3] == PAPER
    finally:
        pygame.quit()


@pytest.fixture(autouse=True)
def _fonts() -> Iterator[None]:
    pygame.font.init()
    yield


def test_a_broken_egg_is_sketched_open_at_the_top_with_its_top_half_beside_it():
    whole = sketched(Thing(id=1000, kind="egg", shape=Circle(28), position=(160, 120)))
    broken = sketched(
        Thing(id=1000, kind="egg", shape=Circle(28), position=(160, 120), pose="broken")
    )

    assert pixel(whole, 160, 100) != PAPER  # the whole egg's shell is there...
    assert pixel(broken, 160, 100) == PAPER  # ...the broken one's top half isn't
    assert darkest(broken, pygame.Rect(130, 110, 60, 40)) < 120  # its pencilled bottom half
    assert darkest(broken, pygame.Rect(180, 110, 40, 40)) < 120  # and its top half beside it
