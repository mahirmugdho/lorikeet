"""Where the sim's palette sits: one swatch per colour, in a row centred along the bottom.

It's only layout, in canvas pixels, so the mouse and the drawing agree on where each swatch
is, and it's tested without a window.
"""

from __future__ import annotations

from dataclasses import dataclass

from lorikeet.interface import Point


@dataclass(frozen=True)
class Palette:
    colors: tuple[str, ...]
    """The colour names, left to right: `LORIKEET_PIECE_COLORS`, so only colours detection
    has been set up to tell apart."""

    canvas_size: tuple[int, int]
    swatch: float = 64
    """Each swatch's side, in canvas pixels."""
    gap: float = 24
    """The space between swatches. The bar leaves half of it around the row."""
    margin: float = 24
    """The space between the swatches and the bottom edge of the canvas."""

    def __post_init__(self) -> None:
        if not self.colors:
            raise ValueError("a palette needs at least one colour")

    def swatches(self) -> list[tuple[str, Point]]:
        """Each colour with the centre of its swatch, left to right."""
        width, height = self.canvas_size
        first = (width - self._row_width()) / 2 + self.swatch / 2
        y = height - self.margin - self.swatch / 2
        step = self.swatch + self.gap
        return [(color, (first + i * step, y)) for i, color in enumerate(self.colors)]

    def swatch_at(self, pos: Point) -> str | None:
        """The colour of the swatch under `pos`, or None."""
        half = self.swatch / 2
        for color, (x, y) in self.swatches():
            if abs(pos[0] - x) <= half and abs(pos[1] - y) <= half:
                return color
        return None

    def bar(self) -> tuple[float, float, float, float]:
        """The bar behind the swatches, as (left, top, width, height)."""
        width, height = self.canvas_size
        pad = self.gap / 2
        left = (width - self._row_width()) / 2 - pad
        top = height - self.margin - self.swatch - pad
        return (left, top, self._row_width() + 2 * pad, self.swatch + 2 * pad)

    def covers(self, pos: Point) -> bool:
        """True if `pos` is on the bar, swatches and the gaps between them included."""
        left, top, width, height = self.bar()
        return left <= pos[0] <= left + width and top <= pos[1] <= top + height

    def _row_width(self) -> float:
        return len(self.colors) * self.swatch + (len(self.colors) - 1) * self.gap
