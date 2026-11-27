"""The launcher wires an input, a game, overlays and a renderer together. A fake renderer
stands in for the window here, so none of this needs a display."""

import pygame
import pytest

from lorikeet.app import parse_args, run
from lorikeet.desk.source import DeskSceneSource
from lorikeet.interface import Scene
from lorikeet.view import Circle, Thing, View

SIZE = (320, 180)
SPOT = (5, 5)
RED, BLUE = (255, 0, 0, 255), (0, 0, 255, 255)
EGG = View(things=(Thing(id=1, kind="egg", shape=Circle(5), position=(10, 10)),))


class FakeRenderer:
    """Hands out its scripted events once, and keeps each view and a copy of each layer."""

    size = SIZE

    def __init__(self, events: list[pygame.event.Event] | None = None) -> None:
        self._events = list(events or [])
        self.views: list[View] = []
        self.walls: list[pygame.Surface] = []
        self.layers: list[pygame.Surface] = []

    def events(self) -> list[pygame.event.Event]:
        events, self._events = self._events, []
        return events

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
    """Notes the type of every event it's given, and marks SPOT on the layer when drawn,
    for its first `frames` frames."""

    def __init__(
        self,
        mark: tuple[int, int, int, int],
        frames: int = 99,
        paper: tuple[int, int, int] | None = None,
    ) -> None:
        self.mark = mark
        self.frames = frames
        self.paper = paper  # given, it also puts this colour on the wall at SPOT
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


def test_defaults_are_the_desk_in_a_1920x1080_window_drawn_flat():
    args = parse_args([])

    assert (args.input, args.output, args.renderer, args.size) == (
        "desk",
        "window",
        "flat",
        (1920, 1080),
    )


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

    run(game, source, FakeRenderer(), max_frames=2)

    assert [len(scene.pieces) for scene in game.scenes] == [1, 1]


def test_run_hands_the_renderer_the_games_view():
    renderer = FakeRenderer()

    run(FakeGame(), DeskSceneSource(), renderer, max_frames=1)

    assert renderer.views == [EGG]


def test_run_gives_every_overlay_the_events():
    click = pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(40, 50), button=3)
    overlays = (FakeOverlay(RED), FakeOverlay(BLUE))

    run(FakeGame(), DeskSceneSource(), FakeRenderer([click]), overlays=overlays, max_frames=1)

    assert [pygame.MOUSEBUTTONDOWN in overlay.events for overlay in overlays] == [True, True]


def test_overlays_draw_in_order_onto_the_layer_the_renderer_lays_on_top():
    renderer = FakeRenderer()

    run(FakeGame(), DeskSceneSource(), renderer, (FakeOverlay(RED), FakeOverlay(BLUE)), 1)

    assert renderer.layers[0].get_at(SPOT) == BLUE


def test_the_layer_starts_clear_every_frame():
    renderer = FakeRenderer()

    run(FakeGame(), DeskSceneSource(), renderer, (FakeOverlay(RED, frames=1),), max_frames=2)

    assert renderer.layers[1].get_at(SPOT).a == 0  # drawn on frame 1 only, so gone on frame 2


def test_escape_stops_before_drawing_anything():
    escape = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE)
    renderer = FakeRenderer([escape])

    run(FakeGame(), DeskSceneSource(), renderer, max_frames=5)

    assert renderer.views == []


def test_overlays_put_their_paper_on_the_wall_the_renderer_gets():
    renderer = FakeRenderer()

    run(FakeGame(), DeskSceneSource(), renderer, (FakeOverlay(RED, paper=(0, 200, 0)),), 1)

    assert renderer.walls[0].get_at(SPOT)[:3] == (0, 200, 0)


def test_the_wall_starts_bare_every_frame():
    renderer = FakeRenderer()
    overlay = FakeOverlay(RED, frames=1, paper=(0, 200, 0))

    run(FakeGame(), DeskSceneSource(), renderer, (overlay,), max_frames=2)

    assert renderer.walls[1].get_at(SPOT)[:3] == (255, 255, 255)  # bare wall is white
