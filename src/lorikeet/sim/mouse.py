"""Mouse controls for the sim: click a palette swatch to pick a colour, left-click sticks a
note of that colour on, right-click peels one off.

There's no pygame in here, so it's tested without a window. The launcher passes on pygame's
mouse clicks, already in canvas pixels, which are projector pixels.
"""

from __future__ import annotations

from lorikeet.interface import PieceState, Point, Polygon
from lorikeet.sim.palette import Palette
from lorikeet.sim.source import SimSceneSource

LEFT, RIGHT = 1, 3
"""Mouse button numbers, as SDL (and so pygame) numbers them. The wheel is 4 and 5."""


class SimMouse:
    def __init__(self, source: SimSceneSource, palette: Palette) -> None:
        self._source = source
        self.palette = palette
        self.color = palette.colors[0]
        """The colour of the notes a left-click sticks on: the last swatch clicked."""
        self.show_palette = True
        """While False the palette is put away, and clicks where it was reach the surface."""

    def click(self, pos: Point, button: int) -> None:
        if self.show_palette and self.palette.covers(pos):
            # The palette lies on top of the surface, so a click on it never reaches a note.
            if button == LEFT:
                self.color = self.palette.swatch_at(pos) or self.color
        elif button == LEFT:
            self._source.drop(self.color, pos)
        elif button == RIGHT and (note := self._note_at(pos)) is not None:
            self._source.pick_up(note)

    def _note_at(self, pos: Point) -> int | None:
        """The id of the top note under `pos`, or None.

        HIDDEN notes are skipped: they're already off the surface, waiting out the grace
        period, so there's nothing there to peel. Scenes list notes in the order they went
        on, so the last match is the one on top.
        """
        under = [
            piece.id
            for piece in self._source.latest().pieces
            if piece.state is not PieceState.HIDDEN and _inside(pos, piece.outline)
        ]
        return under[-1] if under else None


def _inside(point: Point, convex: Polygon) -> bool:
    """True if `point` is inside the convex polygon, or on its edge.

    Walking around a convex polygon, a point inside is on the same side of every edge. The
    cross product's sign says which side, whichever way round the corners go.
    """
    x, y = point
    sides = [
        (bx - ax) * (y - ay) - (by - ay) * (x - ax)
        for (ax, ay), (bx, by) in zip(convex, convex[1:] + convex[:1], strict=True)
    ]
    return all(side >= 0 for side in sides) or all(side <= 0 for side in sides)
