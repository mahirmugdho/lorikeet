"""The launcher wires an input to an output and runs a game between them, headless here."""

from collections.abc import Iterator

import pygame
import pytest

from lorikeet.app import parse_args, run
from lorikeet.desk.source import DeskSceneSource
from lorikeet.interface import Scene

# The headless driver has no GPU renderer, so SCALED falls back to a slower one and says so.
pytestmark = pytest.mark.filterwarnings("ignore:no fast renderer available")

GROUND = (90, 120, 150)
RED, BLUE = (255, 0, 0), (0, 0, 255)


@pytest.fixture
def canvas(monkeypatch: pytest.MonkeyPatch) -> Iterator[pygame.Surface]:
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")  # CI has no display
    pygame.display.init()
    yield pygame.display.set_mode((320, 180), pygame.SCALED)
    pygame.quit()


class FakeGame:
    """Keeps every scene it's given, and fills the canvas when drawn."""

    def __init__(self) -> None:
        self.scenes: list[Scene] = []

    def update(self, scene: Scene, dt: float) -> None:
        self.scenes.append(scene)

    def draw(self, canvas: pygame.Surface) -> None:
        canvas.fill(GROUND)


class FakeOverlay:
    """Notes the type of every event it's given, and marks the top-left pixel when drawn."""

    def __init__(self, mark: tuple[int, int, int]) -> None:
        self.mark = mark
        self.events: list[int] = []

    def handle(self, event: pygame.event.Event) -> None:
        self.events.append(event.type)

    def draw(self, canvas: pygame.Surface) -> None:
        canvas.set_at((0, 0), self.mark)


def test_input_defaults_to_the_desk_and_output_to_a_1920x1080_window():
    args = parse_args([])

    assert (args.input, args.output, args.size) == ("desk", "window", (1920, 1080))


def test_size_is_given_as_width_x_height():
    assert parse_args(["--size", "1280x720"]).size == (1280, 720)


def test_a_malformed_size_is_rejected():
    with pytest.raises(SystemExit):
        parse_args(["--size", "1280by720"])


def test_a_size_must_be_positive():
    with pytest.raises(SystemExit):
        parse_args(["--size", "0x720"])


def test_run_gives_the_game_the_sources_scenes(canvas: pygame.Surface):
    source = DeskSceneSource(clock=lambda: 0.0)
    source.drop("yellow", (160, 90))
    game = FakeGame()

    run(game, source, canvas, max_frames=2)

    assert [len(scene.pieces) for scene in game.scenes] == [1, 1]


def test_run_gives_every_overlay_the_events(canvas: pygame.Surface):
    pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(40, 50), button=3))
    overlays = (FakeOverlay(RED), FakeOverlay(BLUE))

    run(FakeGame(), DeskSceneSource(), canvas, overlays=overlays, max_frames=1)

    assert [pygame.MOUSEBUTTONDOWN in overlay.events for overlay in overlays] == [True, True]


def test_run_draws_the_overlays_over_the_game_in_order(canvas: pygame.Surface):
    overlays = (FakeOverlay(RED), FakeOverlay(BLUE))

    run(FakeGame(), DeskSceneSource(), canvas, overlays=overlays, max_frames=1)

    # The game fills the canvas, then red marks the pixel, then blue marks it again.
    assert canvas.get_at((0, 0))[:3] == BLUE
