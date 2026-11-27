"""The launcher wires an input, a game and its windows together: the game window (the
projection) and, at the desk, the desk window. Fake renderers stand in for the windows and a
scripted queue for pygame's input, so none of this needs a display."""

from collections.abc import Callable, Sequence

import pygame
import pytest

from lorikeet.app import Screen, parse_args, run
from lorikeet.desk.source import DeskSceneSource
from lorikeet.interface import Scene
from lorikeet.view import Circle, Thing, View

SIZE = (320, 180)
SPOT = (5, 5)
RED, BLUE = (255, 0, 0, 255), (0, 0, 255, 255)
EGG = View(things=(Thing(id=1, kind="egg", shape=Circle(5), position=(10, 10)),))


def scripted(*events: pygame.event.Event) -> Callable[[], list[pygame.event.Event]]:
    """Stands in for pygame's input queue: hands out `events` once, then nothing."""
    queue = [list(events)]
    return lambda: queue.pop() if queue else []


def event(kind: int, window: str | None = None, **attributes: object) -> pygame.event.Event:
    return pygame.event.Event(kind, {"window": window, **attributes})


class FakeRenderer:
    """Takes the input from its own window (named by `window`), and keeps each view and a copy
    of each wall and layer it's asked to draw."""

    size = SIZE

    def __init__(self, window: str | None = None) -> None:
        self.window = window
        self.views: list[View] = []
        self.walls: list[pygame.Surface] = []
        self.layers: list[pygame.Surface] = []

    def events(self, pending: Sequence[pygame.event.Event]) -> list[pygame.event.Event]:
        return [e for e in pending if getattr(e, "window", None) == self.window]

    def draw(self, view: View, wall: pygame.Surface, layer: pygame.Surface) -> None:
        self.views.append(view)
        self.walls.append(wall.copy())
        self.layers.append(layer.copy())

    def close(self) -> None:
        pass


class FakeGame:
    def __init__(self) -> None:
        self.scenes: list[Scene] = []

    def update(self, scene: Scene, dt: float) -> None:
        self.scenes.append(scene)

    def view(self) -> View:
        return EGG


class FakeOverlay:
    """Notes the type of every event it's given, and marks SPOT on the layer (and, given
    `paper`, on the wall) when drawn, for its first `frames` frames."""

    def __init__(
        self,
        mark: tuple[int, int, int, int],
        frames: int = 99,
        paper: tuple[int, int, int] | None = None,
    ) -> None:
        self.mark = mark
        self.frames = frames
        self.paper = paper
        self.events: list[int] = []

    def handle(self, event: pygame.event.Event) -> None:
        self.events.append(event.type)

    def draw_wall(self, wall: pygame.Surface) -> None:
        if self.paper is not None and self.frames > 0:
            wall.set_at(SPOT, self.paper)

    def draw(self, canvas: pygame.Surface) -> None:
        if self.frames > 0:
            canvas.set_at(SPOT, self.mark)
            self.frames -= 1


def one_window(*overlays: FakeOverlay) -> tuple[FakeRenderer, list[Screen]]:
    renderer = FakeRenderer()
    return renderer, [Screen(renderer, overlays)]


def test_defaults_are_the_desk_and_a_1920x1080_game_window_drawn_flat():
    # The game window is the projection, flat by default; the desk gets its own window.
    args = parse_args([])

    assert (args.input, args.output, args.renderer, args.size) == (
        "desk",
        "window",
        "flat",
        (1920, 1080),
    )


def test_the_game_windows_renderer_can_be_chosen():
    assert parse_args(["--renderer", "sketch"]).renderer == "sketch"


def test_the_default_game_is_nest_from_its_first_level():
    args = parse_args([])

    assert (args.game, args.level) == ("nest", "01-first-hop")


def test_no_game_can_be_chosen_for_an_empty_desk():
    assert parse_args(["--game", "none"]).game == "none"


def test_a_level_that_does_not_exist_is_rejected():
    with pytest.raises(SystemExit):
        parse_args(["--level", "99-nope"])


def test_size_is_given_as_width_x_height():
    assert parse_args(["--size", "1280x720"]).size == (1280, 720)


def test_a_malformed_size_is_rejected():
    with pytest.raises(SystemExit):
        parse_args(["--size", "1280by720"])


def test_a_size_must_be_positive():
    with pytest.raises(SystemExit):
        parse_args(["--size", "0x720"])


def test_run_gives_the_game_the_sources_scenes():
    source = DeskSceneSource(clock=lambda: 0.0)
    source.drop("yellow", (160, 90))
    game = FakeGame()
    _, screens = one_window()

    run(game, source, screens, max_frames=2, poll=scripted())

    assert [len(scene.pieces) for scene in game.scenes] == [1, 1]


def test_every_window_is_handed_the_same_view():
    game_window, desk_window = FakeRenderer(), FakeRenderer("desk")

    run(FakeGame(), DeskSceneSource(), [Screen(game_window), Screen(desk_window)], 1, scripted())

    assert (game_window.views, desk_window.views) == ([EGG], [EGG])


def test_each_windows_overlays_get_only_that_windows_input():
    on_game, on_desk = FakeOverlay(RED), FakeOverlay(BLUE)
    screens = [Screen(FakeRenderer(), (on_game,)), Screen(FakeRenderer("desk"), (on_desk,))]
    click_on_desk = event(pygame.MOUSEBUTTONDOWN, window="desk", pos=(40, 50), button=1)

    run(FakeGame(), DeskSceneSource(), screens, max_frames=1, poll=scripted(click_on_desk))

    assert (on_game.events, on_desk.events) == ([], [pygame.MOUSEBUTTONDOWN])


def test_overlays_draw_in_order_onto_the_layer_the_renderer_lays_on_top():
    renderer, screens = one_window(FakeOverlay(RED), FakeOverlay(BLUE))

    run(FakeGame(), DeskSceneSource(), screens, max_frames=1, poll=scripted())

    assert renderer.layers[0].get_at(SPOT) == BLUE


def test_the_layer_starts_clear_every_frame():
    renderer, screens = one_window(FakeOverlay(RED, frames=1))

    run(FakeGame(), DeskSceneSource(), screens, max_frames=2, poll=scripted())

    assert renderer.layers[1].get_at(SPOT).a == 0  # drawn on frame 1 only, so gone on frame 2


def test_overlays_put_their_paper_on_the_wall_the_renderer_gets():
    renderer, screens = one_window(FakeOverlay(RED, paper=(0, 200, 0)))

    run(FakeGame(), DeskSceneSource(), screens, max_frames=1, poll=scripted())

    assert renderer.walls[0].get_at(SPOT)[:3] == (0, 200, 0)


def test_the_wall_starts_bare_every_frame():
    renderer, screens = one_window(FakeOverlay(RED, frames=1, paper=(0, 200, 0)))

    run(FakeGame(), DeskSceneSource(), screens, max_frames=2, poll=scripted())

    assert renderer.walls[1].get_at(SPOT)[:3] == (255, 255, 255)  # bare wall is white


def test_escape_in_any_window_stops_everything_before_drawing():
    game_window, desk_window = FakeRenderer(), FakeRenderer("desk")
    escape_on_desk = event(pygame.KEYDOWN, window="desk", key=pygame.K_ESCAPE)
    screens = [Screen(game_window), Screen(desk_window)]

    run(FakeGame(), DeskSceneSource(), screens, max_frames=5, poll=scripted(escape_on_desk))

    assert (game_window.views, desk_window.views) == ([], [])


def test_closing_any_window_stops_everything():
    game_window, desk_window = FakeRenderer(), FakeRenderer("desk")
    close_desk = event(pygame.WINDOWCLOSE, window="desk")

    run(
        FakeGame(),
        DeskSceneSource(),
        [Screen(game_window), Screen(desk_window)],
        5,
        scripted(close_desk),
    )

    assert game_window.views == []
