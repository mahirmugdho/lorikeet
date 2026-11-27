"""The sim's overlay: notes drawn as paper over the game's frame, the palette, and the mouse."""

import pygame
import pytest

from lorikeet.sim.mouse import SimMouse
from lorikeet.sim.overlay import PAPER, SimOverlay
from lorikeet.sim.palette import Palette
from lorikeet.sim.source import SimSceneSource

SIZE = (1000, 600)
PALETTE = Palette(("yellow", "pink"), canvas_size=SIZE)
YELLOW_SWATCH = PALETTE.swatches()[0][1]


@pytest.fixture
def now() -> list[float]:
    return [0.0]


@pytest.fixture
def sim(now: list[float]) -> SimSceneSource:
    return SimSceneSource(note_size=100, clock=lambda: now[0])


@pytest.fixture
def overlay(sim: SimSceneSource) -> SimOverlay:
    return SimOverlay(sim, SimMouse(sim, PALETTE))


def drawn(overlay: SimOverlay) -> pygame.Surface:
    canvas = pygame.Surface(SIZE)
    overlay.draw(canvas)
    return canvas


def pixel(canvas: pygame.Surface, point: tuple[float, float]) -> tuple[int, int, int]:
    r, g, b, _ = canvas.get_at((int(point[0]), int(point[1])))
    return (r, g, b)


def test_a_note_on_the_surface_is_drawn_as_paper_of_its_colour(
    sim: SimSceneSource, overlay: SimOverlay
):
    sim.drop("pink", (300, 200))

    assert pixel(drawn(overlay), (300, 200)) == PAPER["pink"]


def test_a_peeled_note_is_not_drawn_while_it_waits_out_the_grace_period(
    sim: SimSceneSource, overlay: SimOverlay, now: list[float]
):
    note = sim.drop("pink", (300, 200))
    now[0] = 1.0
    sim.pick_up(note)  # HIDDEN to games, but no longer on the surface

    assert pixel(drawn(overlay), (300, 200)) != PAPER["pink"]


def test_the_palette_shows_a_swatch_of_each_colour(overlay: SimOverlay):
    assert pixel(drawn(overlay), YELLOW_SWATCH) == PAPER["yellow"]


def test_tab_hides_the_palette(overlay: SimOverlay):
    overlay.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_TAB))

    assert pixel(drawn(overlay), YELLOW_SWATCH) != PAPER["yellow"]


def test_a_click_reaches_the_sim(sim: SimSceneSource, overlay: SimOverlay):
    overlay.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(300, 200), button=1))

    assert len(sim.latest().pieces) == 1
