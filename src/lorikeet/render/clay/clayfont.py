"""A hand-rolled clay font: letters made of thin ropes of clay, the way the go disc's "go" is
(`kinds.go_disc`), and the way you'd letter a sign on a clay set.

Each letter is drawn as a few strokes, lines and arcs, like handwriting in one continuous
pen, and each stroke becomes a rope of clay laid along it (a chain of `RoundCone`s with
round joints). Dots (on i, j, !, ?) are little balls of clay.

Letters are measured in x-heights: the baseline is at 0, a lowercase letter's top at 1, a
capital's or a tall letter's top at `CAP`, and a descender's bottom at `DESCENT`. A letter
is built once, at `X_HEIGHT` pixels to the x-height (`glyph`), and scaled for each size of
text, so any text in any size is just copies of letters already built (see `scene.py`).
"""

from __future__ import annotations

import itertools
import math
from collections.abc import Iterator

import numpy as np

from lorikeet.render.clay.figure import Figure, Piece
from lorikeet.render.clay.shapes import Ellipsoid, RoundCone

CAP, DESCENT = 1.45, -0.55
X_HEIGHT = 24.0
"""Pixels to the x-height that letters are built at."""
ROPE = 0.12
"""The ropes' radius, in x-heights: bold enough to read across a room, thin enough to look
rolled by hand."""
DOT = 1.3
"""A dot's radius, in rope radii."""
SPACE = 0.55
"""A space's width, in x-heights."""
TRACKING = 0.22
"""The gap between letters, in x-heights (on top of each letter's own width)."""
LETTER_COLOUR = (82, 72, 64)
"""Dark, neutral clay: words never add colour that could look like a note to the camera."""

Point = tuple[float, float]
Stroke = list[Point]


def _line(*points: Point) -> Stroke:
    return list(points)


def _arc(cx: float, cy: float, rx: float, ry: float, start: float, end: float) -> Stroke:
    """An arc of an ellipse, from `start` to `end` degrees (counterclockwise from the right;
    going down if `end` is less), as points about 10 degrees apart."""
    steps = max(2, math.ceil(abs(end - start) / 10))
    return [
        (
            cx + rx * math.cos(math.radians(start + (end - start) * i / steps)),
            cy + ry * math.sin(math.radians(start + (end - start) * i / steps)),
        )
        for i in range(steps + 1)
    ]


def _ring(cx: float, cy: float, rx: float, ry: float) -> Stroke:
    return _arc(cx, cy, rx, ry, 90, 450)


def _then(*parts: Stroke) -> Stroke:
    """Strokes joined end to end into one."""
    joined: Stroke = []
    for part in parts:
        joined += part
    return joined


# Each letter: its width (in x-heights), its strokes, and its dots.
LETTERS: dict[str, tuple[float, list[Stroke], list[Point]]] = {
    "a": (0.95, [_ring(0.45, 0.5, 0.42, 0.5), _line((0.87, 1.0), (0.87, 0.0))], []),
    "b": (0.95, [_line((0.08, CAP), (0.08, 0.0)), _ring(0.5, 0.5, 0.42, 0.5)], []),
    "c": (0.85, [_arc(0.48, 0.5, 0.42, 0.5, 40, 320)], []),
    "d": (0.95, [_ring(0.45, 0.5, 0.42, 0.5), _line((0.87, CAP), (0.87, 0.0))], []),
    "e": (0.9, [_then(_line((0.06, 0.5), (0.9, 0.5)), _arc(0.48, 0.5, 0.42, 0.5, 0, 315))], []),
    "f": (
        0.6,
        [
            _then(_line((0.25, 0.0), (0.25, 1.15)), _arc(0.5, 1.15, 0.25, 0.28, 180, 30)),
            _line((0.0, 0.95), (0.58, 0.95)),
        ],
        [],
    ),
    "g": (
        0.95,
        [
            _ring(0.45, 0.5, 0.42, 0.5),
            _then(_line((0.87, 1.0), (0.87, -0.2)), _arc(0.47, -0.2, 0.4, 0.33, 0, -165)),
        ],
        [],
    ),
    "h": (
        0.9,
        [
            _line((0.08, CAP), (0.08, 0.0)),
            _then(_arc(0.47, 0.6, 0.39, 0.4, 180, 0), _line((0.86, 0.6), (0.86, 0.0))),
        ],
        [],
    ),
    "i": (0.2, [_line((0.1, 1.0), (0.1, 0.0))], [(0.1, 1.38)]),
    "j": (
        0.42,
        [_then(_line((0.3, 1.0), (0.3, -0.25)), _arc(0.05, -0.25, 0.25, 0.28, 0, -160))],
        [(0.3, 1.38)],
    ),
    "k": (
        0.85,
        [
            _line((0.08, CAP), (0.08, 0.0)),
            _line((0.8, 1.0), (0.1, 0.38)),
            _line((0.38, 0.62), (0.85, 0.0)),
        ],
        [],
    ),
    "l": (
        0.25,
        [_then(_line((0.1, CAP), (0.1, 0.12)), _arc(0.22, 0.12, 0.12, 0.12, 180, 300))],
        [],
    ),
    "m": (
        1.35,
        [
            _line((0.08, 1.0), (0.08, 0.0)),
            _then(_arc(0.37, 0.65, 0.29, 0.35, 180, 0), _line((0.66, 0.65), (0.66, 0.0))),
            _then(_arc(0.95, 0.65, 0.29, 0.35, 180, 0), _line((1.24, 0.65), (1.24, 0.0))),
        ],
        [],
    ),
    "n": (
        0.9,
        [
            _line((0.08, 1.0), (0.08, 0.0)),
            _then(_arc(0.47, 0.6, 0.39, 0.4, 180, 0), _line((0.86, 0.6), (0.86, 0.0))),
        ],
        [],
    ),
    "o": (0.92, [_ring(0.46, 0.5, 0.44, 0.5)], []),
    "p": (0.95, [_line((0.08, 1.0), (0.08, DESCENT)), _ring(0.5, 0.5, 0.42, 0.5)], []),
    "q": (0.95, [_ring(0.45, 0.5, 0.42, 0.5), _line((0.87, 1.0), (0.87, DESCENT))], []),
    "r": (0.68, [_line((0.08, 1.0), (0.08, 0.0)), _arc(0.44, 0.55, 0.36, 0.42, 180, 40)], []),
    "s": (
        0.8,
        [_then(_arc(0.4, 0.75, 0.32, 0.25, 30, 270), _arc(0.4, 0.25, 0.34, 0.25, 90, -150))],
        [],
    ),
    "t": (
        0.62,
        [
            _then(_line((0.25, 1.3), (0.25, 0.18)), _arc(0.45, 0.18, 0.2, 0.18, 180, 310)),
            _line((0.0, 1.0), (0.58, 1.0)),
        ],
        [],
    ),
    "u": (
        0.9,
        [
            _then(_line((0.08, 1.0), (0.08, 0.4)), _arc(0.47, 0.4, 0.39, 0.4, 180, 360)),
            _line((0.86, 1.0), (0.86, 0.0)),
        ],
        [],
    ),
    "v": (0.86, [_line((0.0, 1.0), (0.43, 0.0), (0.86, 1.0))], []),
    "w": (1.25, [_line((0.0, 1.0), (0.31, 0.0), (0.62, 0.75), (0.93, 0.0), (1.24, 1.0))], []),
    "x": (0.85, [_line((0.05, 1.0), (0.82, 0.0)), _line((0.82, 1.0), (0.05, 0.0))], []),
    "y": (0.88, [_line((0.04, 1.0), (0.45, 0.1)), _line((0.86, 1.0), (0.28, DESCENT))], []),
    "z": (0.85, [_line((0.08, 1.0), (0.8, 1.0), (0.06, 0.0), (0.84, 0.0))], []),
    "A": (1.1, [_line((0.0, 0.0), (0.55, CAP), (1.1, 0.0)), _line((0.22, 0.52), (0.88, 0.52))], []),
    "B": (
        1.0,
        [
            _line((0.08, 0.0), (0.08, CAP)),
            _then(
                _line((0.08, CAP), (0.5, CAP)),
                _arc(0.5, 1.1, 0.32, 0.35, 90, -90),
                _line((0.5, 0.75), (0.08, 0.75)),
            ),
            _then(
                _line((0.08, 0.75), (0.55, 0.75)),
                _arc(0.55, 0.375, 0.38, 0.375, 90, -90),
                _line((0.55, 0.0), (0.08, 0.0)),
            ),
        ],
        [],
    ),
    "C": (1.15, [_arc(0.66, 0.725, 0.6, 0.725, 40, 320)], []),
    "D": (
        1.12,
        [
            _line((0.08, 0.0), (0.08, CAP)),
            _then(
                _line((0.08, CAP), (0.4, CAP)),
                _arc(0.4, 0.725, 0.66, 0.725, 90, -90),
                _line((0.4, 0.0), (0.08, 0.0)),
            ),
        ],
        [],
    ),
    "E": (
        0.92,
        [
            _line((0.88, CAP), (0.08, CAP), (0.08, 0.0), (0.9, 0.0)),
            _line((0.08, 0.75), (0.72, 0.75)),
        ],
        [],
    ),
    "F": (
        0.88,
        [_line((0.88, CAP), (0.08, CAP), (0.08, 0.0)), _line((0.08, 0.75), (0.72, 0.75))],
        [],
    ),
    "G": (
        1.22,
        [
            _then(
                _arc(0.66, 0.725, 0.6, 0.725, 40, 340),
                _line((1.22, 0.48), (1.22, 0.65), (0.78, 0.65)),
            )
        ],
        [],
    ),
    "H": (
        1.08,
        [
            _line((0.08, CAP), (0.08, 0.0)),
            _line((1.0, CAP), (1.0, 0.0)),
            _line((0.08, 0.75), (1.0, 0.75)),
        ],
        [],
    ),
    "I": (0.25, [_line((0.12, CAP), (0.12, 0.0))], []),
    "J": (
        0.85,
        [_then(_line((0.75, CAP), (0.75, 0.38)), _arc(0.4, 0.38, 0.35, 0.38, 0, -180))],
        [],
    ),
    "K": (
        1.0,
        [
            _line((0.08, CAP), (0.08, 0.0)),
            _line((0.95, CAP), (0.1, 0.55)),
            _line((0.42, 0.83), (1.0, 0.0)),
        ],
        [],
    ),
    "L": (0.86, [_line((0.08, CAP), (0.08, 0.0), (0.86, 0.0))], []),
    "M": (1.3, [_line((0.08, 0.0), (0.08, CAP), (0.65, 0.4), (1.22, CAP), (1.22, 0.0))], []),
    "N": (1.1, [_line((0.08, 0.0), (0.08, CAP), (1.0, 0.0), (1.0, CAP))], []),
    "O": (1.36, [_ring(0.68, 0.725, 0.64, 0.725)], []),
    "P": (
        0.98,
        [
            _line((0.08, 0.0), (0.08, CAP)),
            _then(
                _line((0.08, CAP), (0.52, CAP)),
                _arc(0.52, 1.05, 0.4, 0.4, 90, -90),
                _line((0.52, 0.65), (0.08, 0.65)),
            ),
        ],
        [],
    ),
    "Q": (1.4, [_ring(0.68, 0.725, 0.64, 0.725), _line((0.85, 0.35), (1.38, -0.12))], []),
    "R": (
        1.02,
        [
            _line((0.08, 0.0), (0.08, CAP)),
            _then(
                _line((0.08, CAP), (0.52, CAP)),
                _arc(0.52, 1.05, 0.4, 0.4, 90, -90),
                _line((0.52, 0.65), (0.08, 0.65)),
            ),
            _line((0.5, 0.65), (1.0, 0.0)),
        ],
        [],
    ),
    "S": (
        0.98,
        [_then(_arc(0.49, 1.08, 0.4, 0.37, 30, 270), _arc(0.49, 0.36, 0.44, 0.36, 90, -150))],
        [],
    ),
    "T": (1.0, [_line((0.0, CAP), (1.0, CAP)), _line((0.5, CAP), (0.5, 0.0))], []),
    "U": (
        1.08,
        [
            _then(
                _line((0.08, CAP), (0.08, 0.5)),
                _arc(0.54, 0.5, 0.46, 0.5, 180, 360),
                _line((1.0, 0.5), (1.0, CAP)),
            )
        ],
        [],
    ),
    "V": (1.1, [_line((0.0, CAP), (0.55, 0.0), (1.1, CAP))], []),
    "W": (1.5, [_line((0.0, CAP), (0.38, 0.0), (0.75, 1.1), (1.12, 0.0), (1.5, CAP))], []),
    "X": (1.02, [_line((0.05, CAP), (0.98, 0.0)), _line((0.98, CAP), (0.05, 0.0))], []),
    "Y": (1.04, [_line((0.0, CAP), (0.52, 0.7), (1.04, CAP)), _line((0.52, 0.7), (0.52, 0.0))], []),
    "Z": (1.02, [_line((0.08, CAP), (0.96, CAP), (0.05, 0.0), (0.98, 0.0))], []),
    "0": (0.95, [_ring(0.48, 0.725, 0.44, 0.725)], []),
    "1": (0.65, [_line((0.08, 1.12), (0.45, CAP), (0.45, 0.0))], []),
    "2": (
        0.95,
        [_then(_arc(0.47, 1.05, 0.4, 0.4, 160, -35), _line((0.8, 0.82), (0.06, 0.0), (0.92, 0.0)))],
        [],
    ),
    "3": (
        0.95,
        [_then(_arc(0.46, 1.1, 0.37, 0.35, 150, -90), _arc(0.46, 0.38, 0.42, 0.38, 90, -150))],
        [],
    ),
    "4": (1.0, [_line((0.72, 0.0), (0.72, CAP), (0.04, 0.42), (0.98, 0.42))], []),
    "5": (
        0.95,
        [
            _then(
                _line((0.86, CAP), (0.15, CAP), (0.1, 0.82)),
                _arc(0.48, 0.45, 0.42, 0.45, 140, -150),
            )
        ],
        [],
    ),
    "6": (0.95, [_then(_line((0.68, CAP), (0.13, 0.5)), _ring(0.5, 0.45, 0.42, 0.45))], []),
    "7": (0.95, [_line((0.04, CAP), (0.92, CAP), (0.32, 0.0))], []),
    "8": (0.95, [_ring(0.48, 1.08, 0.34, 0.37), _ring(0.48, 0.38, 0.42, 0.38)], []),
    "9": (0.95, [_ring(0.47, 1.0, 0.42, 0.45), _line((0.89, 1.0), (0.4, 0.0))], []),
    "'": (0.2, [_line((0.1, CAP), (0.06, 1.05))], []),
    "!": (0.28, [_line((0.13, CAP), (0.13, 0.45))], [(0.13, 0.0)]),
    "?": (
        0.85,
        [_then(_arc(0.43, 1.1, 0.36, 0.35, 160, -80), _line((0.43, 0.75), (0.43, 0.45)))],
        [(0.43, 0.0)],
    ),
    ".": (0.2, [], [(0.1, 0.0)]),
    ",": (0.22, [_line((0.12, 0.05), (0.03, -0.25))], []),
    ":": (0.2, [], [(0.1, 0.0), (0.1, 0.8)]),
    "-": (0.6, [_line((0.04, 0.55), (0.56, 0.55))], []),
    "…": (0.9, [], [(0.1, 0.0), (0.45, 0.0), (0.8, 0.0)]),
}
"""Every letter the font has. Anything else is drawn as a `?`."""


def glyph(char: str) -> Figure:
    """One letter, as a clay figure `X_HEIGHT` pixels to the x-height, its baseline's left
    end at the origin, facing the camera (x right, z up)."""
    _, strokes, dots = LETTERS[char if char in LETTERS else "?"]
    rope = ROPE * X_HEIGHT
    pieces = []
    for stroke in strokes:
        for (x0, y0), (x1, y1) in _segments(stroke):
            a = (x0 * X_HEIGHT, 0.0, y0 * X_HEIGHT)
            b = (x1 * X_HEIGHT, 0.0, y1 * X_HEIGHT)
            pieces.append(Piece(RoundCone(a, b, rope, rope), "letter"))
    for x, y in dots:
        size = DOT * rope
        ball = Ellipsoid((x * X_HEIGHT, 0.0, y * X_HEIGHT + 0.3 * rope), (size, size, size))
        pieces.append(Piece(ball, "letter"))
    return Figure(
        tuple(pieces),
        {"letter": LETTER_COLOUR},
        lump_height=0.25,
        lump_size=5.0,
        seam_depth=0.0,
        mottle=0.05,
        mottle_size=6.0,
        seed=sum(map(ord, char)),
    )


def layout(text: str) -> tuple[list[tuple[str, float]], float]:
    """Where each letter of `text` goes along the line, in x-heights from the line's left
    end, and how long the line is. Spaces take up room but have no letter."""
    placed = []
    x = 0.0
    for char in text:
        if char == " ":
            x += SPACE
            continue
        shown = char if char in LETTERS else "?"
        placed.append((shown, x))
        x += LETTERS[shown][0] + TRACKING
    return placed, max(0.0, x - TRACKING)


def _segments(stroke: Stroke) -> Iterator[tuple[Point, Point]]:
    """A stroke's consecutive pairs of points, skipping any that are the same point."""
    for a, b in itertools.pairwise(stroke):
        if np.hypot(b[0] - a[0], b[1] - a[1]) > 1e-6:
            yield a, b
