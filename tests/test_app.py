"""The launcher wires an input to an output and runs a game between them, headless here."""

from collections.abc import Iterator

import pygame
import pytest

from lorikeet.app import parse_args, run
from lorikeet.sim.source import SimSceneSource
from lorikeet.viewer import BACKGROUND, Viewer

# The headless driver has no GPU renderer, so SCALED falls back to a slower one and says so.
pytestmark = pytest.mark.filterwarnings("ignore:no fast renderer available")

MARK = (255, 0, 0)


@pytest.fixture
def canvas(monkeypatch: pytest.MonkeyPatch) -> Iterator[pygame.Surface]:
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")  # CI has no display
    pygame.display.init()
    yield pygame.display.set_mode((320, 180), pygame.SCALED)
    pygame.quit()


class FakeOverlay:
    """Notes the type of every event it's given, and marks the top-left pixel when drawn."""

    def __init__(self) -> None:
        self.events: list[int] = []

    def handle(self, event: pygame.event.Event) -> None:
        self.events.append(event.type)

    def draw(self, canvas: pygame.Surface) -> None:
        canvas.set_at((0, 0), MARK)


def test_output_defaults_to_a_window_with_a_1920x1080_canvas():
    args = parse_args([])

    assert (args.input, args.output, args.size) == ("sim", "window", (1920, 1080))


def test_size_is_given_as_width_x_height():
    assert parse_args(["--size", "1280x720"]).size == (1280, 720)


def test_a_malformed_size_is_rejected():
    with pytest.raises(SystemExit):
        parse_args(["--size", "1280by720"])


def test_a_size_must_be_positive():
    with pytest.raises(SystemExit):
        parse_args(["--size", "0x720"])


def test_run_draws_the_game_from_the_sources_scenes(canvas: pygame.Surface):
    source = SimSceneSource()
    source.drop("yellow", (160, 90))  # its left edge is at x=110

    run(Viewer(), source, canvas, max_frames=2)

    assert canvas.get_at((110, 90))[:3] != BACKGROUND


def test_run_gives_the_overlay_the_events(canvas: pygame.Surface):
    pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(40, 50), button=3))
    overlay = FakeOverlay()

    run(Viewer(), SimSceneSource(), canvas, overlay=overlay, max_frames=1)

    assert pygame.MOUSEBUTTONDOWN in overlay.events


def test_run_draws_the_overlay_over_the_game(canvas: pygame.Surface):
    run(Viewer(), SimSceneSource(), canvas, overlay=FakeOverlay(), max_frames=1)

    # The viewer fills the whole canvas, so the mark survives only if it was drawn after.
    assert canvas.get_at((0, 0))[:3] == MARK
