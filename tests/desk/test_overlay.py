"""The desk's overlay: notes drawn as paper over the game's frame, the palette, and the mouse."""

import pygame
import pytest

from lorikeet.desk.mouse import DeskMouse
from lorikeet.desk.overlay import PAPER, DeskOverlay
from lorikeet.desk.palette import Palette
from lorikeet.desk.source import DeskSceneSource

SIZE = (1000, 600)
PALETTE = Palette(("yellow", "pink"), canvas_size=SIZE)
YELLOW_SWATCH = PALETTE.swatches()[0][1]


@pytest.fixture
def now() -> list[float]:
    return [0.0]


@pytest.fixture
def desk(now: list[float]) -> DeskSceneSource:
    return DeskSceneSource(note_size=100, clock=lambda: now[0])


@pytest.fixture
def overlay(desk: DeskSceneSource) -> DeskOverlay:
    return DeskOverlay(desk, DeskMouse(desk, PALETTE))


def drawn(overlay: DeskOverlay) -> pygame.Surface:
    canvas = pygame.Surface(SIZE)
    overlay.draw(canvas)
    return canvas


def pixel(canvas: pygame.Surface, point: tuple[float, float]) -> tuple[int, int, int]:
    r, g, b, _ = canvas.get_at((int(point[0]), int(point[1])))
    return (r, g, b)


def test_a_note_on_the_surface_is_drawn_as_paper_of_its_colour(
    desk: DeskSceneSource, overlay: DeskOverlay
):
    desk.drop("pink", (300, 200))

    assert pixel(drawn(overlay), (300, 200)) == PAPER["pink"]


def test_a_peeled_note_is_not_drawn_while_it_waits_out_the_grace_period(
    desk: DeskSceneSource, overlay: DeskOverlay, now: list[float]
):
    note = desk.drop("pink", (300, 200))
    now[0] = 1.0
    desk.pick_up(note)  # HIDDEN to games, but no longer on the surface

    assert pixel(drawn(overlay), (300, 200)) != PAPER["pink"]


def test_the_palette_shows_a_swatch_of_each_colour(overlay: DeskOverlay):
    assert pixel(drawn(overlay), YELLOW_SWATCH) == PAPER["yellow"]


def test_tab_hides_the_palette(overlay: DeskOverlay):
    overlay.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_TAB))

    assert pixel(drawn(overlay), YELLOW_SWATCH) != PAPER["yellow"]


def press(pos: tuple[int, int]) -> pygame.event.Event:
    return pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pos, button=1)


def release(pos: tuple[int, int]) -> pygame.event.Event:
    return pygame.event.Event(pygame.MOUSEBUTTONUP, pos=pos, button=1)


def test_a_click_reaches_the_desk(desk: DeskSceneSource, overlay: DeskOverlay):
    overlay.handle(press((300, 200)))
    overlay.handle(release((300, 200)))

    assert len(desk.latest().pieces) == 1


def test_a_held_note_follows_the_mouse(overlay: DeskOverlay):
    overlay.handle(press((300, 200)))
    overlay.handle(pygame.event.Event(pygame.MOUSEMOTION, pos=(600, 300)))

    canvas = drawn(overlay)
    # Drawn see-through, as it's in the hand rather than on the surface.
    assert pixel(canvas, (600, 300)) not in {(0, 0, 0), PAPER["yellow"]}
    assert pixel(canvas, (300, 200)) == (0, 0, 0)


def test_the_wheel_turns_the_held_note(desk: DeskSceneSource, overlay: DeskOverlay):
    overlay.handle(press((300, 200)))
    overlay.handle(pygame.event.Event(pygame.MOUSEWHEEL, x=0, y=18))  # 18 steps of 5 degrees
    overlay.handle(release((300, 200)))

    # A quarter turn clockwise takes the top-left corner to the top right (y grows down).
    assert desk.latest().pieces[0].outline[0] == pytest.approx((350, 150))
