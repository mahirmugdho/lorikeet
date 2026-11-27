"""Renderers: each draws a game's View its own way, and owns the window it draws in (ADR 0008).

The launcher picks a renderer and tells it the output: a window on this screen, or the
projector. Each frame it hands over the game's `View` and the overlay layer: a transparent,
canvas-sized surface with the desk's notes and the debug overlay on it. The renderer draws
the view, lays the layer on top without looking inside it, and shows the frame. The window
is the renderer's, so the mouse and keyboard come from it too, and it passes them back.

Renderers import nothing from Lorikeet but the view (and the interface's point types), so
they can't depend on any one game. `tests/test_boundaries.py` checks that.
"""

from __future__ import annotations

from typing import Protocol

import pygame

from lorikeet.view import View


class Renderer(Protocol):
    @property
    def size(self) -> tuple[int, int]:
        """The canvas, in projector pixels. The overlay layer must be this size."""
        ...

    def events(self) -> list[pygame.event.Event]:
        """The mouse and keyboard input since the last call, positions in canvas pixels."""
        ...

    def draw(self, view: View, layer: pygame.Surface) -> None:
        """Draw `view`, lay `layer` on top of it unchanged, and show the frame.

        `layer` holds premultiplied alpha (each colour already multiplied by its alpha), so
        lay it on with premultiplied blending: src + dst * (1 - src alpha). That's the one
        blend that stays right when see-through things overlap, so the overlays look the
        same under every renderer."""
        ...

    def close(self) -> None:
        """Close the window."""
        ...
