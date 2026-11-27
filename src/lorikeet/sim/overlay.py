"""The sim's overlay: what the sim draws on top of the game's frame, and its mouse input.

With real notes, the paper is on the wall and the projector shines on it. In the sim there's
no paper, so the overlay draws each note over the game's frame, then the palette. The
launcher draws it after the game, and the game never knows it's there.
"""

from __future__ import annotations

import pygame

from lorikeet.interface import PieceState, Polygon, square
from lorikeet.sim.mouse import SimMouse
from lorikeet.sim.source import SimSceneSource

PAPER = {
    "yellow": (250, 222, 90),
    "pink": (245, 135, 180),
    "green": (135, 215, 125),
    "blue": (110, 180, 240),
    "orange": (250, 165, 75),
    "purple": (185, 145, 230),
    "red": (235, 95, 90),
}
"""How each colour name looks on screen. This is only for drawing the sim's notes: detection
keeps its own thresholds for each name, calibrated per room."""

UNKNOWN_PAPER = (170, 170, 170)
"""For a colour name the table above doesn't know."""

_BAR = (0, 0, 0, 150)  # translucent, so the game shows through behind the palette
_CHOSEN = (245, 245, 245)


class SimOverlay:
    def __init__(self, source: SimSceneSource, mouse: SimMouse) -> None:
        self._source = source
        self._mouse = mouse

    def handle(self, event: pygame.event.Event) -> None:
        if event.type == pygame.MOUSEBUTTONDOWN:
            self._mouse.click(event.pos, event.button)
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_TAB:
            self._mouse.show_palette = not self._mouse.show_palette

    def draw(self, canvas: pygame.Surface) -> None:
        for piece in self._source.latest().pieces:
            # Games still hear about a HIDDEN piece for the grace period, but it has been
            # peeled off: there's no paper on the wall any more.
            if piece.state is not PieceState.HIDDEN:
                _paper(canvas, piece.color, piece.outline)
        if self._mouse.show_palette:
            self._draw_palette(canvas)

    def _draw_palette(self, canvas: pygame.Surface) -> None:
        palette = self._mouse.palette
        left, top, width, height = (round(n) for n in palette.bar())
        bar = pygame.Surface((width, height), pygame.SRCALPHA)
        pygame.draw.rect(bar, _BAR, bar.get_rect(), border_radius=12)
        canvas.blit(bar, (left, top))
        for color, center in palette.swatches():
            _paper(canvas, color, square(center, palette.swatch))
            if color == self._mouse.color:
                pygame.draw.polygon(canvas, _CHOSEN, square(center, palette.swatch + 10), 3)


def _paper(canvas: pygame.Surface, color: str, outline: Polygon) -> None:
    """A note of `color`, with a darker rim so touching notes stay easy to tell apart."""
    fill = PAPER.get(color, UNKNOWN_PAPER)
    pygame.draw.polygon(canvas, fill, outline)
    pygame.draw.polygon(canvas, tuple(channel * 3 // 4 for channel in fill), outline, 2)
