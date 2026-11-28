"""The flat renderer owns its window, draws a View in flat shapes, and lays the overlays on top."""

import math
from collections.abc import Iterator

import pygame
import pytest

from lorikeet.render.flat import BACKDROP, FlatRenderer, native_pixel_settings, stretch_warning
from lorikeet.render.flat_looks import DEFAULT_FILL
from lorikeet.view import Circle, Outline, Text, Thing, View

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


def bare_wall() -> pygame.Surface:
    wall = pygame.Surface(SIZE)
    wall.fill((255, 255, 255))
    return wall


def shown(
    renderer: FlatRenderer,
    view: View,
    layer: pygame.Surface | None = None,
    wall: pygame.Surface | None = None,
) -> pygame.Surface:
    """What the window shows after drawing `view` on `wall` (bare if not given), with `layer`
    (empty if not given) on top."""
    renderer.draw(view, wall or bare_wall(), layer or pygame.Surface(SIZE, pygame.SRCALPHA))
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
    # A kind the renderer has no look for: plain and shadowless, so only the turn shows.
    upright = Thing(id=1, kind="plank", shape=BAR, position=(160, 90), angle=math.pi / 2)

    screen = shown(renderer, View(things=(upright,)))

    # Turned a quarter, the bar stands up: it covers a point 20 px above its centre, and no
    # longer the point 20 px to its right.
    assert pixel(screen, 160, 70) != BACKDROP
    assert pixel(screen, 180, 90) == BACKDROP


def test_the_overlay_layer_is_laid_on_top_of_everything(renderer: FlatRenderer):
    egg = Thing(id=1, kind="egg", shape=Circle(10), position=(100, 90))
    layer = pygame.Surface(SIZE, pygame.SRCALPHA)
    layer.set_at((100, 90), RED)
    wall = bare_wall()
    wall.fill((0, 200, 0), pygame.Rect(80, 70, 40, 40))  # paper under the egg

    assert pixel(shown(renderer, View(things=(egg,)), layer, wall), 100, 90) == RED


def test_the_picture_lands_on_the_wall_like_light_on_paper(renderer: FlatRenderer):
    # What you see is the projection times the colour of what it lands on: on green paper
    # the egg is tinted green, as it would be on the real wall.
    egg = Thing(id=1, kind="egg", shape=Circle(10), position=(100, 90))
    plain = pixel(shown(renderer, View(things=(egg,))), 100, 90)
    wall = bare_wall()
    wall.fill((0, 200, 0), pygame.Rect(80, 70, 40, 40))

    on_paper = pixel(shown(renderer, View(things=(egg,)), wall=wall), 100, 90)

    expected = (0, plain[1] * 200 / 255, 0)
    assert all(abs(a - b) <= 2 for a, b in zip(on_paper, expected, strict=True))


def test_projector_output_explains_a_missing_display(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    pygame.init()
    try:
        with pytest.raises(SystemExit, match="Is the projector plugged in"):
            FlatRenderer("projector", SIZE, display=7)
    finally:
        pygame.quit()


WAYLAND_SESSION = {"WAYLAND_DISPLAY": "wayland-0", "DISPLAY": ":0"}


def test_in_a_wayland_session_on_linux_it_draws_through_wayland():
    # Through X11 (XWayland), a desktop with any display scaling can stretch the window,
    # the projector's included. Through Wayland, the window gets the display's own pixels.
    assert native_pixel_settings(WAYLAND_SESSION, "linux") == {"SDL_VIDEODRIVER": "wayland"}


def test_in_an_x11_session_it_leaves_the_driver_alone():
    assert native_pixel_settings({"DISPLAY": ":0"}, "linux") == {}


def test_a_driver_you_chose_yourself_is_kept():
    chosen = {**WAYLAND_SESSION, "SDL_VIDEODRIVER": "x11"}

    assert native_pixel_settings(chosen, "linux") == {}


def test_on_windows_it_handles_display_scaling_itself():
    assert native_pixel_settings({}, "win32") == {"SDL_WINDOWS_DPI_AWARENESS": "permonitorv2"}


def test_on_macos_it_changes_nothing():
    assert native_pixel_settings({}, "darwin") == {}


def test_no_warning_when_the_desktop_gives_the_display_all_its_pixels():
    assert stretch_warning(1, (1920, 1080), [(1920, 1080), (1280, 720)]) is None


def test_a_warning_names_both_sizes_when_the_display_could_show_more():
    warning = stretch_warning(1, (1280, 720), [(1920, 1080), (1280, 720)])

    assert warning is not None and "1280x720" in warning and "1920x1080" in warning


def test_no_warning_when_the_display_lists_no_modes():
    assert stretch_warning(1, (1920, 1080), []) is None


LEDGE = Outline(((-60, -30), (60, -30), (60, 30), (-60, 30)))  # at (160, 90): 100..220, 60..120


def test_terrain_has_rounded_corners(renderer: FlatRenderer):
    ledge = Thing(id=1, kind="terrain", shape=LEDGE, position=(160, 90))

    screen = shown(renderer, View(things=(ledge,)))

    assert pixel(screen, 160, 90) != BACKDROP  # filled in the middle
    # Its top-left corner is rounded off. The soft shadow, offset down and right, can still
    # reach it by a level or two, so it's compared within a small tolerance.
    corner = pixel(screen, 100, 60)
    assert max(abs(a - b) for a, b in zip(corner, BACKDROP, strict=True)) <= 4


def test_terrain_casts_a_soft_shadow_below_it(renderer: FlatRenderer):
    ledge = Thing(id=1, kind="terrain", shape=LEDGE, position=(160, 90))

    shadow = pixel(shown(renderer, View(things=(ledge,))), 160, 124)  # just under its bottom

    assert sum(shadow) < sum(BACKDROP)


def test_a_note_is_outlined_just_outside_its_edge(renderer: FlatRenderer):
    note = Thing(id=1, kind="note", shape=LEDGE, position=(160, 90))  # 100..220, 60..120

    screen = shown(renderer, View(things=(note,)))

    assert min(min(pixel(screen, x, y)) for x in range(130, 190) for y in range(48, 60)) < 120


def test_a_notes_paper_is_left_unlit(renderer: FlatRenderer):
    # Light on the paper would shift its colour for the camera (ADR 0006), so only the
    # outline, outside the edge, is drawn.
    note = Thing(id=1, kind="note", shape=LEDGE, position=(160, 90))

    screen = shown(renderer, View(things=(note,)))

    inside = pygame.Rect(108, 68, 104, 44)
    assert pygame.transform.average_color(screen, inside)[:3] == BACKDROP


@pytest.mark.parametrize("pose", ["off", "on"])
def test_the_go_spot_leaves_its_middle_unlit_for_the_note_on_it(renderer: FlatRenderer, pose: str):
    # Light inside the spot would land on the real note there and shift its colour (ADR 0006).
    go = Thing(id=1, kind="go", shape=Circle(40), position=(160, 90), pose=pose)

    assert pixel(shown(renderer, View(things=(go,))), 160, 90) == BACKDROP


def test_a_kind_without_a_look_gets_the_plain_default(renderer: FlatRenderer):
    thing = Thing(id=1, kind="mystery", shape=Circle(20), position=(160, 90))

    assert pixel(shown(renderer, View(things=(thing,))), 160, 90) == DEFAULT_FILL


def test_text_is_written_centred_where_it_is(renderer: FlatRenderer):
    words = Thing(id=1, kind="message", shape=Text("Hello", size=40), position=(160, 90))

    screen = shown(renderer, View(things=(words,)))

    around = pygame.Rect(100, 70, 120, 40)
    assert pygame.transform.average_color(screen, around)[:3] != BACKDROP
    assert pygame.transform.average_color(screen, pygame.Rect(0, 0, 60, 40))[:3] == BACKDROP


def test_the_egg_has_a_darker_rim_so_it_shows_up_on_paper(renderer: FlatRenderer):
    # The picture lands on paper notes like light, so a nearly white egg on a green note is
    # just slightly brighter green. A darker rim keeps its outline visible.
    egg = Thing(id=1, kind="egg", shape=Circle(20), position=(160, 90))

    screen = shown(renderer, View(things=(egg,)))

    assert sum(pixel(screen, 179, 90)) < sum(pixel(screen, 160, 90)) - 60


def test_the_game_window_takes_its_own_input_and_leaves_the_desks(renderer: FlatRenderer):
    mine = pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(10, 10), button=1, window=None)
    desks = pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(10, 10), button=1, window="desk")

    assert renderer.events([mine, desks]) == [mine]


def test_a_broken_egg_is_open_at_the_top_with_its_top_half_lying_beside_it(
    renderer: FlatRenderer,
):
    whole = Thing(id=1000, kind="egg", shape=Circle(28), position=(160, 120))
    broken = Thing(id=1000, kind="egg", shape=Circle(28), position=(160, 120), pose="broken")

    intact, cracked = (shown(renderer, View(things=(t,))).copy() for t in (whole, broken))

    assert pixel(intact, 160, 100) != BACKDROP  # the whole egg's shell is there...
    assert pixel(cracked, 160, 100) == BACKDROP  # ...the broken one's top half isn't
    assert pixel(cracked, 160, 135) != BACKDROP  # its bottom half is
    assert pixel(cracked, 197, 130) != BACKDROP  # and its top half lies beside it
