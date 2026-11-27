"""The debug overlay: what games are told, drawn over whatever is running. Press D.

For each piece it draws the outline, styled by state, with "#id colour state" just above.
It reads the same scenes the game gets, so it works with any game, input and output. That
makes it the way to check detection and tracking on the wall, and the desk's rules on a
laptop. Players never need it, so it starts hidden.

It draws only edges, never inside an outline. On the projector, light inside a real note's
outline shifts the note's colour for the camera (ADR 0006). For the same reason the state
shows only in the edge (docs/ROADMAP.md, Phase 2): heavy for SETTLED, thin for MOVING, grey
for HIDDEN.
"""

from __future__ import annotations

import pygame

from lorikeet.interface import Piece, PieceState, SceneSource

INK = (35, 35, 35)

_EDGES = {
    PieceState.SETTLED: (INK, 5),
    PieceState.MOVING: (INK, 2),
    PieceState.HIDDEN: ((125, 125, 125), 2),
}
"""Colour and width of each state's edge."""


class DebugOverlay:
    def __init__(self, source: SceneSource) -> None:
        pygame.font.init()
        self._font = pygame.font.Font(None, 28)  # None picks the font pygame ships with
        self._source = source
        self.shown = False

    def handle(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN and event.key == pygame.K_d:
            self.shown = not self.shown

    def draw(self, canvas: pygame.Surface) -> None:
        if not self.shown:
            return
        for piece in self._source.latest().pieces:
            color, width = _EDGES[piece.state]
            pygame.draw.polygon(canvas, color, piece.outline, width)
            self._label(canvas, piece, color)

    def _label(self, canvas: pygame.Surface, piece: Piece, color: tuple[int, int, int]) -> None:
        """'#id colour state' just above the piece, so its text never lands on the note."""
        text = self._font.render(f"#{piece.id} {piece.color} {piece.state.value}", True, color)
        left = min(x for x, _ in piece.outline)
        top = min(y for _, y in piece.outline)
        canvas.blit(text, (left, top - text.get_height() - 6))
