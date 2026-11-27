"""Mouse controls for the sim, which handle notes the way hands do on the wall.

- Press on a note to peel it off and hold it. Press on bare surface to take a fresh note of
  the current colour, or on a palette swatch to take one of that colour (it becomes the
  current colour).
- Drag it, and turn it with the wheel while you hold it.
- Let go to stick it down where it is, as a new piece. Let go over the palette, or
  right-click while holding, to put it back.
- Right-click a note on the surface to peel it off for good.

A held note isn't on the surface, so the scene doesn't have it: the camera wouldn't see it
either. There's no pygame in here, so it's tested without a window. The overlay passes on
pygame's mouse events, already in canvas pixels, which are projector pixels.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from lorikeet.interface import Piece, PieceState, Point, Polygon
from lorikeet.sim.palette import Palette
from lorikeet.sim.source import SimSceneSource, turned_square

LEFT, RIGHT = 1, 3
"""Mouse button numbers, as SDL (and so pygame) numbers them."""

TURN_STEP = 5.0
"""Degrees a held note turns per wheel step. Rolling the wheel away from you turns it
clockwise."""


@dataclass
class Held:
    """The note in the hand."""

    color: str
    angle: float
    grip: Point
    """From the cursor to the note's centre, so the note doesn't jump to centre on the
    cursor when you grab it off-centre."""


class SimMouse:
    def __init__(self, source: SimSceneSource, palette: Palette) -> None:
        self._source = source
        self.palette = palette
        self.color = palette.colors[0]
        """The colour of a fresh note taken from bare surface: the last swatch used."""
        self.show_palette = True
        """While False the palette is put away, and clicks where it was reach the surface."""
        self.held: Held | None = None
        self.cursor: Point = (0.0, 0.0)

    def press(self, pos: Point, button: int) -> None:
        self.cursor = pos
        if button == LEFT and self.held is None:
            self.held = self._take(pos)
        elif button == RIGHT:
            self._right_click(pos)

    def move(self, pos: Point) -> None:
        self.cursor = pos

    def release(self, pos: Point, button: int) -> None:
        self.cursor = pos
        if button != LEFT or self.held is None:
            return
        held, self.held = self.held, None
        if not self._on_palette(pos):  # letting go over the palette puts the note back
            center = (pos[0] + held.grip[0], pos[1] + held.grip[1])
            self._source.drop(held.color, center, held.angle)

    def scroll(self, steps: float) -> None:
        if self.held is not None:
            self.held.angle += steps * TURN_STEP

    def held_outline(self) -> Polygon | None:
        """Where the held note is, to draw it, or None if nothing is held."""
        if self.held is None:
            return None
        x, y = self.cursor
        center = (x + self.held.grip[0], y + self.held.grip[1])
        return turned_square(center, self._source.note_size, self.held.angle)

    def _take(self, pos: Point) -> Held | None:
        """What a left press at `pos` picks up, if anything."""
        if self._on_palette(pos):
            # The palette lies on top of the surface, so a press on it never reaches a note.
            swatch = self.palette.swatch_at(pos)
            if swatch is None:
                return None  # the bar between swatches
            self.color = swatch
            return Held(swatch, angle=0.0, grip=(0.0, 0.0))
        piece = self._note_at(pos)
        if piece is None:
            return Held(self.color, angle=0.0, grip=(0.0, 0.0))
        self._source.pick_up(piece.id)
        cx, cy = piece.center
        return Held(piece.color, _angle(piece.outline), grip=(cx - pos[0], cy - pos[1]))

    def _right_click(self, pos: Point) -> None:
        if self.held is not None:
            self.held = None  # put the held note back
        elif not self._on_palette(pos) and (piece := self._note_at(pos)) is not None:
            self._source.pick_up(piece.id)

    def _on_palette(self, pos: Point) -> bool:
        return self.show_palette and self.palette.covers(pos)

    def _note_at(self, pos: Point) -> Piece | None:
        """The top note under `pos`, or None.

        HIDDEN notes are skipped: they're already off the surface, waiting out the grace
        period, so there's nothing there to touch. Scenes list notes in the order they went
        on, so the last match is the one on top.
        """
        under = [
            piece
            for piece in self._source.latest().pieces
            if piece.state is not PieceState.HIDDEN and _inside(pos, piece.outline)
        ]
        return under[-1] if under else None


def _angle(outline: Polygon) -> float:
    """How far a sim note is turned, in degrees clockwise on screen.

    `turned_square` lists the corners from the top left, so the first edge is the note's
    top edge, and its direction is the turn.
    """
    (x0, y0), (x1, y1) = outline[0], outline[1]
    return math.degrees(math.atan2(y1 - y0, x1 - x0))


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
