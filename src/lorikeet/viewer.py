"""A debug view of the scene: every piece's outline, id, colour name and state.

The launcher runs it when there's no game, so you can see exactly what games are told. It
works like a game (it sees only `Scene`s and a canvas), so it runs the same on any input and
any output.

It keeps the background dark and draws only edges. On the projector, anything bright or
coloured inside a real note's outline shifts the note's colour for the camera (ADR 0006).
For the same reason, the state shows only in the edge (docs/ROADMAP.md, Phase 2): heavy for
SETTLED, thin for MOVING, grey for HIDDEN.
"""

from __future__ import annotations

import pygame

from lorikeet.interface import Piece, PieceState, Scene

BACKGROUND = (24, 24, 24)
"""Near black, and neutral, so it adds as little light and colour as possible to real notes."""

_EDGES = {
    PieceState.SETTLED: ((235, 235, 235), 5),
    PieceState.MOVING: ((235, 235, 235), 2),
    PieceState.HIDDEN: ((110, 110, 110), 2),
}
"""Colour and width of each state's edge."""


class Viewer:
    def __init__(self) -> None:
        pygame.font.init()
        self._font = pygame.font.Font(None, 28)  # None picks the font pygame ships with
        self._scene = Scene(time=0.0)

    def update(self, scene: Scene, dt: float) -> None:
        self._scene = scene

    def draw(self, canvas: pygame.Surface) -> None:
        canvas.fill(BACKGROUND)
        for piece in self._scene.pieces:
            color, width = _EDGES[piece.state]
            pygame.draw.polygon(canvas, color, piece.outline, width)
            self._label(canvas, piece, color)

    def _label(self, canvas: pygame.Surface, piece: Piece, color: tuple[int, int, int]) -> None:
        """'#id colour state' just above the piece, so its text never lands on the note."""
        text = self._font.render(f"#{piece.id} {piece.color} {piece.state.value}", True, color)
        left = min(x for x, _ in piece.outline)
        top = min(y for _, y in piece.outline)
        canvas.blit(text, (left, top - text.get_height() - 6))
