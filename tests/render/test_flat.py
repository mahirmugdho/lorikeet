"""The flat renderer owns its window, draws a View in flat shapes, and lays the overlays on top."""

import math
from collections.abc import Iterator

import pygame
import pytest

from lorikeet.render.flat import BACKDROP, FlatRenderer
from lorikeet.view import Circle, Outline, Thing, View

# The headless driver has no GPU renderer, so SCALED falls back to a slower one and says so.
pytestmark = pytest.mark.filterwarnings("ignore:no fast renderer available")

SIZE = (320, 180)
RED = (255, 0, 0)
BAR = Outline(((-30, -3), (30, -3), (30, 3), (-30, 3)))  # 60 px wide, 6 px tall


@pytest.fixture
def renderer(monkeypatch: pytest.MonkeyPatch) -> Iterator[FlatRenderer]:
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")  # CI has no display
    pygame.init()
    flat = FlatRenderer("window", SIZE, display=0)
    yield flat
    flat.close()
    pygame.quit()


def shown(
    renderer: FlatRenderer, view: View, layer: pygame.Surface | None = None
) -> pygame.Surface:
    """What the window shows after drawing `view`, with `layer` (empty if not given) on top."""
    renderer.draw(view, layer or pygame.Surface(SIZE, pygame.SRCALPHA))
    screen = pygame.display.get_surface()
    assert screen is not None
    return screen


def pixel(surface: pygame.Surface, x: int, y: int) -> tuple[int, int, int]:
    r, g, b, _ = surface.get_at((x, y))
    return (r, g, b)


def test_the_canvas_is_the_size_asked_for(renderer: FlatRenderer):
    assert renderer.size == SIZE


def test_an_empty_view_is_all_backdrop(renderer: FlatRenderer):
    assert pygame.transform.average_color(shown(renderer, View()))[:3] == BACKDROP


def test_a_thing_is_drawn_where_it_is(renderer: FlatRenderer):
    egg = Thing(id=1, kind="egg", shape=Circle(10), position=(100, 90))

    assert pixel(shown(renderer, View(things=(egg,))), 100, 90) != BACKDROP


def test_an_outline_is_turned_by_its_angle(renderer: FlatRenderer):
    upright = Thing(id=1, kind="terrain", shape=BAR, position=(160, 90), angle=math.pi / 2)

    screen = shown(renderer, View(things=(upright,)))

    # Turned a quarter, the bar stands up: it covers a point 20 px above its centre, and no
    # longer the point 20 px to its right.
    assert pixel(screen, 160, 70) != BACKDROP
    assert pixel(screen, 180, 90) == BACKDROP


def test_the_overlay_layer_is_laid_on_top(renderer: FlatRenderer):
    egg = Thing(id=1, kind="egg", shape=Circle(10), position=(100, 90))
    layer = pygame.Surface(SIZE, pygame.SRCALPHA)
    layer.set_at((100, 90), RED)

    assert pixel(shown(renderer, View(things=(egg,)), layer), 100, 90) == RED


def test_projector_output_explains_a_missing_display(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    pygame.init()
    try:
        with pytest.raises(SystemExit, match="Is the projector plugged in"):
            FlatRenderer("projector", SIZE, display=7)
    finally:
        pygame.quit()
