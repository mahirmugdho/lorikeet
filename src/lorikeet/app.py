"""The launcher: picks an input and an output, and runs a game between them.

Input and output are two separate choices:

- input: where scenes come from. `sim` for now; `camera` arrives with detection.
- output: where frames go. `window` opens a window on this screen. `projector` fills the
  projector's display, borderless, at its native resolution.

The game in the middle sees only `Scene`s and a canvas in projector pixels, so it can't tell
which input or output it's running on (ADR 0004). This module is the only place that knows,
and `tests/test_boundaries.py` stops games from importing it.

Settings come from the environment (see `.env.example`): `uv run --env-file .env lorikeet`.
"""

from __future__ import annotations

import argparse
import os
from collections.abc import Sequence
from typing import Protocol

import pygame

from lorikeet.interface import Scene, SceneSource
from lorikeet.sim.mouse import SimMouse
from lorikeet.sim.overlay import SimOverlay
from lorikeet.sim.palette import Palette
from lorikeet.sim.source import SimSceneSource
from lorikeet.viewer import Viewer

FPS = 60


class Game(Protocol):
    """What the launcher needs from a game. A game matches it by having these methods; it
    never imports this module."""

    def update(self, scene: Scene, dt: float) -> None:
        """Take the newest scene. `dt` is the seconds since the last update."""
        ...

    def draw(self, canvas: pygame.Surface) -> None:
        """Draw the whole frame. The canvas is in projector pixels, whatever the output."""
        ...


class Overlay(Protocol):
    """Something an input draws over the game's frame, which also gets the mouse and
    keyboard: the sim's paper notes and palette. The camera input will have none. The game
    never sees it: on the wall, notes are the only input."""

    def handle(self, event: pygame.event.Event) -> None: ...

    def draw(self, canvas: pygame.Surface) -> None: ...


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    # By default SDL minimises a fullscreen window when it loses focus, so clicking on the
    # laptop screen would make the projector go blank.
    os.environ.setdefault("SDL_VIDEO_MINIMIZE_ON_FOCUS_LOSS", "0")
    pygame.init()
    try:
        canvas = _open_output(args.output, args.size, args.display)
        source = _open_sim()
        palette = Palette(tuple(_piece_colors()), canvas.get_size())
        overlay = SimOverlay(source, SimMouse(source, palette))
        width, height = canvas.get_size()
        print(f"lorikeet: {args.input} -> {args.output}, canvas {width}x{height}")
        print(
            "pick a colour from the palette, left-click sticks a note on, right-click peels "
            "it off, Tab hides the palette, Esc quits"
        )
        run(Viewer(), source, canvas, overlay=overlay)
    finally:
        pygame.quit()
    return 0


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="lorikeet", description="Run Lorikeet with a chosen input and output."
    )
    parser.add_argument("--input", choices=["sim"], default="sim", help="where notes come from")
    parser.add_argument("--output", choices=["window", "projector"], default="window")
    parser.add_argument(
        "--size",
        type=_size,
        default=(1920, 1080),
        metavar="WxH",
        help="the window's canvas, in projector pixels (default: 1920x1080)",
    )
    parser.add_argument(
        "--display",
        type=int,
        default=int(os.environ.get("LORIKEET_DISPLAY_INDEX", "1")),
        help="the projector's display index (default: LORIKEET_DISPLAY_INDEX, or 1)",
    )
    return parser.parse_args(argv)


def run(
    game: Game,
    source: SceneSource,
    canvas: pygame.Surface,
    overlay: Overlay | None = None,
    max_frames: int | None = None,
) -> None:
    """Each frame: handle input, give the game the newest scene, draw it, draw the overlay
    over it, show it. Stops on Esc or when the window closes, or after `max_frames` (for
    tests). Mouse positions arrive in canvas pixels, whatever the window's size.
    """
    clock = pygame.time.Clock()
    frames = 0
    while max_frames is None or frames < max_frames:
        for event in pygame.event.get():
            if event.type == pygame.QUIT or (
                event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE
            ):
                return
            if overlay is not None:
                overlay.handle(event)
        dt = clock.tick(FPS) / 1000  # also waits, so the loop runs at most FPS times a second
        game.update(source.latest(), dt)
        game.draw(canvas)
        if overlay is not None:
            overlay.draw(canvas)
        pygame.display.flip()
        frames += 1


def _open_output(output: str, size: tuple[int, int], display: int) -> pygame.Surface:
    pygame.display.set_caption("Lorikeet")
    if output == "projector":
        return _open_projector(display)
    # SCALED keeps the canvas at `size` however big the window is, and maps mouse positions
    # back onto the canvas, so the game always works in projector pixels.
    return pygame.display.set_mode(size, pygame.SCALED | pygame.RESIZABLE)


def _open_projector(display: int) -> pygame.Surface:
    sizes = pygame.display.get_desktop_sizes()
    if display >= len(sizes):
        raise SystemExit(
            f"lorikeet: no display {display}, only {len(sizes)}: {sizes}. Is the projector "
            "plugged in, and set to extend the desktop rather than mirror it?"
        )
    pygame.display.set_mode(sizes[display], display=display)
    # Fullscreen at the desktop's own resolution, so one canvas pixel is one projector pixel.
    # The other kind (desktop=False) changes the video mode, which can rescale the picture.
    pygame.Window.from_display_module().set_fullscreen(desktop=True)
    canvas = pygame.display.get_surface()  # fetched again, as going fullscreen can replace it
    if canvas is None:
        raise SystemExit("lorikeet: the projector window closed as it went fullscreen")
    return canvas


def _open_sim() -> SimSceneSource:
    return SimSceneSource(
        note_size=float(os.environ.get("LORIKEET_NOTE_SIZE", "100")),
        settle_seconds=float(os.environ.get("LORIKEET_SETTLE_SECONDS", "0.2")),
        hidden_seconds=float(os.environ.get("LORIKEET_HIDDEN_SECONDS", "2")),
    )


def _piece_colors() -> list[str]:
    """The colour names set up for this room, in the order `LORIKEET_PIECE_COLORS` lists them."""
    names = os.environ.get("LORIKEET_PIECE_COLORS", "yellow,pink,green,blue").split(",")
    return [name.strip() for name in names if name.strip()] or ["yellow"]


def _size(text: str) -> tuple[int, int]:
    """'1920x1080' -> (1920, 1080)."""
    try:
        width, height = (int(part) for part in text.lower().split("x"))
    except ValueError:
        raise argparse.ArgumentTypeError(f"expected WIDTHxHEIGHT, got {text!r}") from None
    if width <= 0 or height <= 0:
        raise argparse.ArgumentTypeError(f"both sides must be positive, got {text!r}")
    return width, height
