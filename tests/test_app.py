"""The launcher wires an input to an output and runs a game between them, headless here."""

import pygame
import pytest

from lorikeet.app import parse_args, run
from lorikeet.sim.source import SimSceneSource
from lorikeet.viewer import BACKGROUND, Viewer


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


# The headless driver has no GPU renderer, so SCALED falls back to a slower one and says so.
@pytest.mark.filterwarnings("ignore:no fast renderer available")
def test_run_draws_the_game_from_the_sources_scenes(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")  # CI has no display
    pygame.display.init()
    try:
        canvas = pygame.display.set_mode((320, 180), pygame.SCALED)
        source = SimSceneSource()
        source.drop("yellow", (160, 90))  # its left edge is at x=110

        run(Viewer(), source, canvas, max_frames=2)

        assert canvas.get_at((110, 90))[:3] != BACKGROUND
    finally:
        pygame.quit()


@pytest.mark.filterwarnings("ignore:no fast renderer available")
def test_run_passes_mouse_clicks_on_in_canvas_pixels(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    pygame.display.init()
    try:
        canvas = pygame.display.set_mode((320, 180), pygame.SCALED)
        clicks: list[tuple[tuple[int, int], int]] = []
        pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(40, 50), button=3))

        run(Viewer(), SimSceneSource(), canvas, max_frames=1, on_click=lambda *c: clicks.append(c))

        assert clicks == [((40, 50), 3)]
    finally:
        pygame.quit()
