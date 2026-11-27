"""The desk's overlay: notes sketched as paper over the game's frame, the palette, and the
mouse."""

import numpy as np
import pygame
import pytest

from lorikeet.desk.mouse import DeskMouse
from lorikeet.desk.overlay import PAPER, DeskOverlay
from lorikeet.desk.palette import Palette
from lorikeet.desk.source import DeskSceneSource

SIZE = (1000, 600)
PALETTE = Palette(("yellow", "pink"), canvas_size=SIZE)
YELLOW_SWATCH = PALETTE.swatches()[0][1]
WHITE = (255, 255, 255)
HINT_BAND = pygame.Rect(0, 430, 1000, 60)  # just above the palette bar, whose top is at y=500
LIGHT = (200, 200, 200)


@pytest.fixture
def now() -> list[float]:
    return [0.0]


@pytest.fixture
def desk(now: list[float]) -> DeskSceneSource:
    return DeskSceneSource(note_size=100, clock=lambda: now[0])


@pytest.fixture
def overlay(desk: DeskSceneSource, now: list[float]) -> DeskOverlay:
    return DeskOverlay(desk, DeskMouse(desk, PALETTE), clock=lambda: now[0])


def drawn(overlay: DeskOverlay, ground: tuple[int, int, int] = (0, 0, 0)) -> pygame.Surface:
    canvas = pygame.Surface(SIZE)
    canvas.fill(ground)
    overlay.draw(canvas)
    return canvas


def on_wall(overlay: DeskOverlay) -> pygame.Surface:
    """What the desk puts on the wall: white where it's bare, paper where notes are."""
    wall = pygame.Surface(SIZE)
    wall.fill(WHITE)
    overlay.draw_wall(wall)
    return wall


def band_is_empty(canvas: pygame.Surface) -> bool:
    return pygame.transform.average_color(canvas, HINT_BAND)[:3] == (0, 0, 0)


def pixel(canvas: pygame.Surface, point: tuple[float, float]) -> tuple[int, int, int]:
    r, g, b, _ = canvas.get_at((int(point[0]), int(point[1])))
    return (r, g, b)


def test_a_note_on_the_surface_is_drawn_as_paper_of_its_colour(
    desk: DeskSceneSource, overlay: DeskOverlay
):
    desk.drop("pink", (300, 200))

    assert pixel(on_wall(overlay), (300, 200)) == PAPER["pink"]


def test_stuck_down_notes_are_on_the_wall_not_on_top_of_the_game(
    desk: DeskSceneSource, overlay: DeskOverlay
):
    # On top they'd hide the egg passing through a zone note; on the wall, the game's
    # picture lands on them like projected light on paper.
    desk.drop("pink", (300, 200))

    assert pixel(drawn(overlay), (300, 200)) == (0, 0, 0)


def test_a_peeled_note_is_not_drawn_while_it_waits_out_the_grace_period(
    desk: DeskSceneSource, overlay: DeskOverlay, now: list[float]
):
    note = desk.drop("pink", (300, 200))
    now[0] = 1.0
    desk.pick_up(note)  # HIDDEN to games, but no longer on the surface

    assert pixel(on_wall(overlay), (300, 200)) == WHITE


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


def test_a_note_casts_a_soft_shadow_below_it(desk: DeskSceneSource, overlay: DeskOverlay):
    desk.drop("pink", (300, 200))  # its bottom edge is at y=250

    assert sum(pixel(on_wall(overlay), (300, 258))) < sum(WHITE)


def test_the_lines_hold_still_within_a_boil_frame(
    desk: DeskSceneSource, overlay: DeskOverlay, now: list[float]
):
    desk.drop("pink", (300, 200))
    first = pygame.image.tobytes(on_wall(overlay), "RGB")
    now[0] = 0.05  # still the first tenth of a second

    assert pygame.image.tobytes(on_wall(overlay), "RGB") == first


def test_the_lines_are_redrawn_on_the_next_boil_frame(
    desk: DeskSceneSource, overlay: DeskOverlay, now: list[float]
):
    desk.drop("pink", (300, 200))
    first = pygame.image.tobytes(on_wall(overlay), "RGB")
    now[0] = 0.1  # the next tenth of a second

    assert pygame.image.tobytes(on_wall(overlay), "RGB") != first


def test_an_empty_desk_shows_how_to_start(overlay: DeskOverlay):
    assert not band_is_empty(drawn(overlay))


def test_the_hint_goes_once_a_note_is_on_the_desk(desk: DeskSceneSource, overlay: DeskOverlay):
    desk.drop("pink", (300, 200))

    assert band_is_empty(drawn(overlay))


def layered(overlay: DeskOverlay, ground: tuple[int, int, int]) -> pygame.Surface:
    """Drawn the way renderers show it: onto a clear layer, then laid over the frame with
    premultiplied blending (ADR 0008)."""
    layer = pygame.Surface(SIZE, pygame.SRCALPHA)
    overlay.draw(layer)
    frame = pygame.Surface(SIZE)
    frame.fill(ground)
    frame.blit(layer, (0, 0), special_flags=pygame.BLEND_PREMULTIPLIED)
    return frame


def largest_difference(a: pygame.Surface, b: pygame.Surface) -> int:
    pixels_a = pygame.surfarray.array3d(a).astype(int)
    pixels_b = pygame.surfarray.array3d(b).astype(int)
    return int(np.abs(pixels_a - pixels_b).max())


def test_on_a_clear_layer_it_looks_the_same_as_drawn_straight_onto_the_frame(
    desk: DeskSceneSource, overlay: DeskOverlay
):
    # Every renderer lays the overlay layer over its own frame, so drawing onto a clear
    # layer has to look like drawing straight onto the frame. The held note is the hard case:
    # it's see-through, over its own see-through shadow.
    desk.drop("pink", (300, 200))
    overlay.handle(press((600, 300)))

    assert largest_difference(drawn(overlay, LIGHT), layered(overlay, LIGHT)) <= 2


def test_the_hint_looks_the_same_on_a_clear_layer(overlay: DeskOverlay):
    # The text's soft edges are see-through too.
    assert largest_difference(drawn(overlay, LIGHT), layered(overlay, LIGHT)) <= 2
