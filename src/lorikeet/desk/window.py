"""The desk's own window: where you play when there's no camera.

With the desk as input, two windows open. The game window is the projection: what goes on
the projector, drawn by whichever renderer was picked, the same whatever the input. This one,
on the laptop, shows the same game drawn in pencil (the sketch looks), with the desk's paper
notes and palette on it, and all the mouse work happens here.

The game is drawn on a canvas the size of the game window, in projector pixels, then scaled
to fit this window. Mouse positions are scaled back, so the desk works in projector pixels
like everything else. It's a renderer like any other (it matches `lorikeet.render.Renderer`).

Drawing the desk and scaling it down each take about 5 ms at 1920x1080, and the game window
needs about 5 ms of a frame's 16.7. Both in one frame would make that frame late, so the desk
window splits them: one frame it draws, the next it scales and shows. It updates 30 times a
second, and the projection keeps its 60.
"""

from __future__ import annotations

from collections.abc import Sequence

import pygame

from lorikeet.render.sketch import SketchLooks
from lorikeet.view import View

TITLE = "Lorikeet desk"
LETTERBOX = (60, 58, 54)
"""Behind the canvas when the window's shape doesn't match it."""


class DeskWindow:
    def __init__(self, canvas_size: tuple[int, int], scale: float = 0.6) -> None:
        """A window `scale` times the canvas size, which the player can resize."""
        width, height = canvas_size
        self._canvas = pygame.Surface(canvas_size)
        self.window = pygame.Window(
            TITLE, size=(round(width * scale), round(height * scale)), resizable=True
        )
        self._looks = SketchLooks()
        self._drawn = False  # whether the canvas holds a frame that hasn't been shown yet

    @property
    def size(self) -> tuple[int, int]:
        """The canvas, in projector pixels: the game window's size."""
        return self._canvas.get_size()

    def events(self, pending: Sequence[pygame.event.Event]) -> list[pygame.event.Event]:
        """Input from this window only, with mouse positions turned into canvas pixels."""
        return [self._on_canvas(e) for e in pending if getattr(e, "window", None) is self.window]

    def draw(self, view: View, wall: pygame.Surface, layer: pygame.Surface) -> None:
        """Every other call draws the desk onto the canvas; the calls in between show it."""
        if self._drawn:
            self._show()
        else:
            self._draw_canvas(view, wall, layer)
        self._drawn = not self._drawn

    def close(self) -> None:
        self.window.destroy()

    def _draw_canvas(self, view: View, wall: pygame.Surface, layer: pygame.Surface) -> None:
        canvas = self._canvas
        canvas.fill(self._looks.backdrop)
        for thing in view.back_to_front():
            self._looks.draw(canvas, thing)
        canvas.blit(wall, (0, 0), special_flags=pygame.BLEND_MULT)  # see lorikeet.render
        canvas.blit(layer, (0, 0), special_flags=pygame.BLEND_PREMULTIPLIED)

    def _show(self) -> None:
        scale, left, top = self._fit()
        shown = self.window.get_surface()
        shown.fill(LETTERBOX)
        width, height = self.size
        size = (max(1, round(width * scale)), max(1, round(height * scale)))
        shown.blit(pygame.transform.smoothscale(self._canvas, size), (round(left), round(top)))
        self.window.flip()

    def _fit(self) -> tuple[float, float, float]:
        """How the canvas fits the window as it is now: its scale, and where its top-left
        corner sits (centred, with letterboxing on the sides that don't fill)."""
        window_w, window_h = self.window.size
        width, height = self.size
        scale = min(window_w / width, window_h / height)
        return scale, (window_w - width * scale) / 2, (window_h - height * scale) / 2

    def _on_canvas(self, event: pygame.event.Event) -> pygame.event.Event:
        if not hasattr(event, "pos"):
            return event
        scale, left, top = self._fit()
        x, y = event.pos
        attributes = {**event.dict, "pos": ((x - left) / scale, (y - top) / scale)}
        return pygame.event.Event(event.type, attributes)
