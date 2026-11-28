"""The launcher: picks an input, a renderer and an output, and runs a game between them.

- game: what's played. `nest` (the default), or `none` for an empty desk.
- input: where scenes come from. `desk` for now; `camera` arrives with detection.
- renderer: how the game window draws the game's `View` (ADR 0008): `flat` (the default),
  `sketch` (pencil on paper) or `clay` (a stop-motion clay set, in Panda3D).
- output: where the game window goes. `window` on this screen, or `projector`.

The game window is the projection: it shows only what would be projected, whatever the
input. With the desk as input, a second window opens, the desk window, which shows the same
game in pencil with the desk's paper notes and palette. That's where the mouse goes. Without
a projector, both windows sit side by side on this screen.

The game in the middle sees only `Scene`s, and only describes what it shows as a `View`, so
it can't tell which input, renderer or output it's running with (ADR 0004, ADR 0008). The
overlays (the desk's notes, the debug overlay) draw onto a transparent layer that every
renderer lays on top as it is, so they look the same under any renderer. This module is
the only place that knows all the choices, and `tests/test_boundaries.py` stops games from
importing it.

Settings come from the environment (see `.env.example`): `uv run --env-file .env lorikeet`.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Protocol

import pygame

from lorikeet.debug import DebugOverlay
from lorikeet.desk.mouse import DeskMouse
from lorikeet.desk.overlay import DeskOverlay
from lorikeet.desk.palette import Palette
from lorikeet.desk.source import DeskSceneSource
from lorikeet.desk.window import DeskWindow
from lorikeet.games.nest.game import NestGame
from lorikeet.games.nest.level import level_ids, load_level
from lorikeet.interface import Scene, SceneSource
from lorikeet.render import Renderer
from lorikeet.render.flat import FlatRenderer
from lorikeet.render.sketch import SketchRenderer
from lorikeet.view import View

FPS = 60


def _clay(output: str, size: tuple[int, int], display: int) -> Renderer:
    # Imported only when picked: Panda3D is big, and the other renderers don't need it.
    from lorikeet.render.clay.renderer import ClayRenderer

    return ClayRenderer(output, size, display)


RENDERERS: dict[str, Callable[[str, tuple[int, int], int], Renderer]] = {
    "flat": FlatRenderer,
    "sketch": SketchRenderer,
    "clay": _clay,
}
"""Each renderer by name: given the output, the window's canvas size and the projector's
display index, it opens its window."""


class Game(Protocol):
    """What the launcher needs from a game. A game matches it by having these methods; it
    never imports this module."""

    def update(self, scene: Scene, dt: float) -> None:
        """Take the newest scene. `dt` is the seconds since the last update."""
        ...

    def view(self) -> View:
        """What to show this frame, in projector pixels. The game never draws: the renderer
        the player picked does."""
        ...


class Overlay(Protocol):
    """Something besides the game on screen, which also gets the mouse and keyboard: the
    desk, or the debug overlay. The game never sees overlays: on the wall, notes are the
    only input. Both layers are in projector pixels (see `lorikeet.render`)."""

    def handle(self, event: pygame.event.Event) -> None: ...

    def draw_wall(self, wall: pygame.Surface) -> None:
        """Put on the wall what's physically on it, such as the desk's paper notes. The game's
        picture lands on top of it. The wall starts white (bare) each frame."""
        ...

    def draw(self, canvas: pygame.Surface) -> None:
        """Draw what's in front of the wall onto the overlay layer, which is transparent and
        premultiplied: opaque drawing goes on as usual, and anything see-through goes on with
        `premul_alpha()` and `BLEND_PREMULTIPLIED`."""
        ...


@dataclass
class Screen:
    """One window: the renderer that owns it, and the overlays drawn on it and handed its
    input."""

    renderer: Renderer
    overlays: Sequence[Overlay] = ()


class NoGame:
    """Stands in for a game until there is one: it shows nothing."""

    def update(self, scene: Scene, dt: float) -> None:
        pass

    def view(self) -> View:
        return View()


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    pygame.init()  # the overlays draw with pygame, whichever renderer draws the game
    try:
        renderer = RENDERERS[args.renderer](args.output, args.size, args.display)
        screens = [Screen(renderer)]  # what to close, should anything below fail
        try:
            game = _open_game(args.game, args.level, renderer.size)
            source = _open_desk()
            palette = Palette(tuple(_piece_colors()), renderer.size)
            desk = DeskOverlay(source, DeskMouse(source, palette))
            screens = [
                # The debug overlay shows, on the projection, what the game is told.
                Screen(renderer, (DebugOverlay(source),)),
                Screen(DeskWindow(renderer.size), (desk,)),
            ]
            width, height = renderer.size
            print(
                f"lorikeet: {args.game} ({args.level}), {args.input} -> {args.renderer} "
                f"{args.output}, {width}x{height}"
            )
            print(
                "in the desk window: drag notes from the palette or around the surface, roll "
                "the wheel to turn the one you hold, right-click peels one off, Tab hides the "
                "palette. In the game window: D shows what games are told. Esc quits"
            )
            if args.game == "nest":
                print("stick a note on the go spot to start the eggs")
            run(game, source, screens)
        finally:
            # The desk window first: the game window's close shuts pygame's display down.
            for screen in reversed(screens):
                screen.renderer.close()
    finally:
        pygame.quit()
    return 0


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="lorikeet", description="Run Lorikeet with a chosen input, renderer and output."
    )
    parser.add_argument("--game", choices=["nest", "none"], default="nest", help="what to play")
    levels = level_ids()
    parser.add_argument(
        "--level", choices=levels, default=levels[0], help="which Nest level (default: the first)"
    )
    parser.add_argument("--input", choices=["desk"], default="desk", help="where notes come from")
    parser.add_argument(
        "--renderer",
        choices=sorted(RENDERERS),
        default="flat",
        help="how the game window draws the game (default: flat)",
    )
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
    screens: Sequence[Screen],
    max_frames: int | None = None,
    poll: Callable[[], Sequence[pygame.event.Event]] = pygame.event.get,
) -> None:
    """Each frame: read the input once (`poll`) and hand each window's overlays that window's
    events, give the game the newest scene, then for each window, let its overlays draw onto a
    bare wall and a cleared layer, and have its renderer draw the game's view landing on the
    wall, with the layer on top. Every window shows the same view. Stops on Esc in any window
    or when any window closes (whichever kind of window it is), or after `max_frames`
    (tests).
    """
    walls = [pygame.Surface(screen.renderer.size) for screen in screens]
    layers = [pygame.Surface(screen.renderer.size, pygame.SRCALPHA) for screen in screens]
    clock = pygame.time.Clock()
    frames = 0
    while max_frames is None or frames < max_frames:
        pending = list(poll())
        if any(_quits(event) for event in pending):
            return
        for screen in screens:
            events = screen.renderer.events(pending)
            # Again, for renderers whose windows aren't pygame's: their input isn't in
            # `pending`, only in what they hand back.
            if any(_quits(event) for event in events):
                return
            for event in events:
                for overlay in screen.overlays:
                    overlay.handle(event)
        dt = clock.tick(FPS) / 1000  # also waits, so the loop runs at most FPS times a second
        game.update(source.latest(), dt)
        view = game.view()
        for screen, wall, layer in zip(screens, walls, layers, strict=True):
            wall.fill((255, 255, 255))  # bare wall: the picture shows as it is
            layer.fill((0, 0, 0, 0))  # fully transparent: only what overlays draw shows
            for overlay in screen.overlays:
                overlay.draw_wall(wall)
                overlay.draw(layer)
            screen.renderer.draw(view, wall, layer)
        frames += 1


def _quits(event: pygame.event.Event) -> bool:
    """Esc in any window, or closing any window, ends the run."""
    return event.type in (pygame.QUIT, pygame.WINDOWCLOSE) or (
        event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE
    )


def _open_game(name: str, level_id: str, canvas: tuple[int, int]) -> Game:
    if name == "none":
        return NoGame()
    ids = level_ids()
    start = ids.index(level_id)
    # The chosen level first, then the rest in order, coming round to the start again.
    first, *more = (load_level(i) for i in ids[start:] + ids[:start])
    level = first
    if level.size != canvas:
        print(
            f"lorikeet: {level_id} is laid out for {level.size[0]}x{level.size[1]}, but the "
            f"canvas is {canvas[0]}x{canvas[1]}, so it won't fit the screen exactly.",
            file=sys.stderr,
        )
    return NestGame(first, *more)


def _open_desk() -> DeskSceneSource:
    return DeskSceneSource(
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
