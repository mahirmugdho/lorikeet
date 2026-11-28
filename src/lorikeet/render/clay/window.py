"""The clay renderer's window plumbing that doesn't need Panda3D, so it can be tested.

- Where the window goes and how big it is: on this screen, the canvas fitted to the screen;
  on the projector, the whole of that monitor (`monitors`, `fit`).
- How the canvas sits in the window: the clay set is always drawn at the canvas's own size
  (projector pixels), then shown stretched to fill the window, keeping its shape
  (`letterbox`). Then a desktop that scales X11 windows (a KDE Wayland desktop gives an X11
  window 2.25 times the projector's pixels) only costs a quick stretch, not drawing the set
  at 2.25 times the pixels.
- Its keys, as pygame keys (`pygame_key`): the launcher speaks pygame, Panda3D doesn't.
"""

from __future__ import annotations

import math
import re
import shutil
import subprocess
from dataclasses import dataclass

import pygame


@dataclass(frozen=True)
class Monitor:
    """One monitor, in the desktop's own pixels (X11's, the ones a Panda3D window uses)."""

    name: str
    x: int
    y: int
    width: int
    height: int
    primary: bool = False


_MONITOR = re.compile(r"^\s*\d+:\s+\+?(\*?)(\S+)\s+(\d+)/\d+x(\d+)/\d+([+-]\d+)([+-]\d+)")


def parse_monitors(listing: str) -> list[Monitor]:
    """Monitors from `xrandr --listmonitors`, in its order (the primary is usually first),
    which is the order SDL numbers displays in, so `--display` means the same as for the
    pygame renderers."""
    found = []
    for line in listing.splitlines():
        if match := _MONITOR.match(line):
            star, name, width, height, x, y = match.groups()
            found.append(Monitor(name, int(x), int(y), int(width), int(height), star == "*"))
    return found


def monitors() -> list[Monitor]:
    """This desktop's monitors, or an empty list where `xrandr` can't say (not X11)."""
    xrandr = shutil.which("xrandr")
    if xrandr is None:
        return []
    try:
        listing = subprocess.run(
            [xrandr, "--listmonitors"], capture_output=True, text=True, timeout=5, check=True
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    return parse_monitors(listing)


def fit(canvas: tuple[int, int], area: tuple[int, int], share: float = 0.9) -> tuple[int, int]:
    """A window for `canvas` on a screen of `area`: the canvas's own size if it fits in
    `share` of the screen, or else the biggest size of the same shape that does."""
    width, height = canvas
    scale = min(1.0, share * area[0] / width, share * area[1] / height)
    return max(1, math.floor(width * scale)), max(1, math.floor(height * scale))


def letterbox(window: tuple[int, int], canvas: tuple[int, int]) -> tuple[float, float]:
    """How much of the window's width and height the canvas fills when it's stretched as
    big as it'll go without changing shape (1 on the side it fills, less on the other)."""
    window_shape, canvas_shape = window[0] / window[1], canvas[0] / canvas[1]
    return min(1.0, canvas_shape / window_shape), min(1.0, window_shape / canvas_shape)


_RENAMED = {
    "enter": "return",
    "arrow_left": "left",
    "arrow_right": "right",
    "arrow_up": "up",
    "arrow_down": "down",
}
"""Panda3D's names for keys whose pygame names differ."""


def pygame_key(button: str) -> int | None:
    """The pygame key for a Panda3D button name ("escape", "d", "arrow_left"), or None for
    buttons pygame has no key for (mouse buttons, gamepads)."""
    try:
        return pygame.key.key_code(_RENAMED.get(button, button))
    except ValueError:
        return None
