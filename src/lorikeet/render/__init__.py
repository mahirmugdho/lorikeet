"""Renderers: each draws a game's View its own way, and owns the window it draws in (ADR 0008).

The launcher picks a renderer and tells it the output: a window on this screen, or the
projector. Each frame it hands over the game's `View` and two layers from the overlays:

- the wall: what's physically on the wall, white where it's bare and paper where the desk's
  notes are. Projected light lands on whatever it hits, so what you see is the picture times
  the colour of the wall under it. The renderer multiplies its frame by this layer, so on
  the desk the game's picture lands on the paper notes just as it does on the real wall
  (with the camera, the real paper is on the real wall and this layer stays white).
- the overlay layer: transparent, with what's in front of the wall (the desk's palette and
  the note in your hand, the debug overlay). It's laid on top last, without looking inside.

The window is the renderer's, so the mouse and keyboard come from it too, and it passes them
back.

Renderers import nothing from Lorikeet but the view (and the interface's point types), so
they can't depend on any one game. `tests/test_boundaries.py` checks that.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

import pygame

from lorikeet.view import View


class Renderer(Protocol):
    @property
    def size(self) -> tuple[int, int]:
        """The canvas, in projector pixels. The overlay layer must be this size."""
        ...

    def events(self, pending: Sequence[pygame.event.Event]) -> list[pygame.event.Event]:
        """Of the input that just arrived (`pending`, read once for every window), the events
        from this renderer's window, with positions in canvas pixels. With two windows open
        (the game and the desk), each takes only its own. A renderer whose window isn't a
        pygame one ignores `pending` and returns its own input, translated to pygame events."""
        ...

    def draw(self, view: View, wall: pygame.Surface, layer: pygame.Surface) -> None:
        """Draw `view`, multiply it by `wall` (white is bare wall), lay `layer` on top of it
        unchanged, and show the frame.

        `layer` holds premultiplied alpha (each colour already multiplied by its alpha), so
        lay it on with premultiplied blending: src + dst * (1 - src alpha). That's the one
        blend that stays right when see-through things overlap, so the overlays look the
        same under every renderer."""
        ...

    def close(self) -> None:
        """Close the window."""
        ...
