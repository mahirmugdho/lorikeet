"""Lori, the rainbow lorikeet, as a clay figure.

She's built like a plasticine model: a fat round body, a big head pressed on with a soft
neck, and the colours as separate pieces of clay pressed onto it (a red-orange chest, a
purple-blue belly, a yellow-green collar, deep green wings), then a coral beak, oversized
eyes on the sides of her head, and tiny grey feet.

The numbers are in pixels for the game's Lori (radius 34) and scale with `radius`. She faces
+x (right, as in the flat looks), z is up, and y points away from the camera, so -y is her
right side, the one the camera sees. Nothing is quite symmetric, on purpose: the left eye
and wing sit a touch differently from the right, like a model made by hand.
"""

from __future__ import annotations

import numpy as np

from lorikeet.render.clay.figure import Figure, Piece
from lorikeet.render.clay.shapes import Ellipsoid, RoundCone, disc, rotation

CLAYS = {
    "head": (72, 84, 214),  # violet-blue
    "chest": (228, 76, 38),  # red-orange
    "back": (52, 168, 72),  # green: body, back and tail
    "wing": (34, 140, 62),  # a deeper green, so the wings read as their own pieces
    "collar": (176, 214, 52),  # yellow-green
    "belly": (96, 70, 190),  # purple-blue
    "beak": (255, 128, 84),  # coral-orange
    "eye": (236, 233, 226),  # white, a little off so it never glares
    "pupil": (26, 24, 30),
    "feet": (122, 118, 126),  # grey
}
"""Saturated and happy on purpose. Projected, these would read as notes to the camera, but
detection ignores colours inside the game's own things (issue #12)."""

RADIUS = 34.0
"""The radius the numbers below are written for: the game's Lori."""

NECK = (8.0, 0.0, 8.0)
"""Where her head turns and nods from, at radius 34."""
SHOULDER = (-2.0, 14.0, 6.0)
"""Where her far wing hinges, at radius 34 (the near one is at -y)."""
FEET = -32.5
"""How far below her middle the soles of her feet are, at radius 34: she squashes and
stretches from here, so her feet stay planted."""


def lori(radius: float = RADIUS) -> Figure:
    s = radius / RADIUS

    def ball(centre, radii, **turn) -> Ellipsoid:
        return Ellipsoid(_scaled(centre, s), _scaled(radii, s), rotation(**turn))

    def cone(start, end, r1, r2) -> RoundCone:
        return RoundCone(_scaled(start, s), _scaled(end, s), r1 * s, r2 * s)

    head = (9.0, 0.0, 19.0)
    pieces = [
        Piece(ball((0, 0, -6), (24, 21, 23), pitch=10), "back"),
        Piece(ball((-27, 0, -19), (14, 7, 4.5), pitch=35), "back", blend=5 * s),
        Piece(ball(head, (17, 16, 15.5)), "head", blend=9 * s, part="head"),
        Piece(ball((7, 0, 8.5), (15, 17.5, 6), pitch=-15), "collar", blend=2.5 * s),
        Piece(ball((12, 0, -1), (15, 16.5, 13.5)), "chest", blend=2.5 * s),
        Piece(ball((9, 0, -17), (14, 15, 9.5)), "belly", blend=2.5 * s),
    ]
    # Wings: a teardrop each, a broad shoulder tapering back and down to a tip over the
    # tail, as a folded wing does. The far wing sits a touch differently, as by hand.
    for side, lift, part in ((-1, 0.0, "near wing"), (1, 0.6, "far wing")):
        pieces += [
            Piece(
                ball((-2, side * 18.6, -1 + lift), (15, 5.5, 12.5), pitch=18), "wing", 2 * s, part
            ),
            Piece(
                ball((-13, side * 17.6, -7.5 + lift), (13, 4.4, 7), pitch=30), "wing", 8 * s, part
            ),
        ]
    # Tiny feet: an ankle and two stubby toes forward, peeking out under the belly.
    for side, nudge in ((-1, 0.0), (1, 0.4)):
        y = side * 8.0
        pieces += [
            Piece(ball((3.5 + nudge, y, -28.5), (2.8, 2.8, 2.8)), "feet", blend=2 * s),
            Piece(cone((4, y, -30), (9.5, y - 1.8, -31.6), 2.1, 1.6), "feet", blend=1 * s),
            Piece(cone((4, y, -30), (9, y + 2.2, -31.8), 2.1, 1.6), "feet", blend=1 * s),
        ]
    pieces += [
        Piece(cone((22, 0, 20), (31, 0, 13.5), 6.0, 2.2), "beak", blend=2 * s, part="head"),
        Piece(cone((29.5, 0, 15), (31.5, 0, 10.5), 2.6, 1.3), "beak", 1.5 * s, part="head"),
        Piece(cone((21, 0, 14.5), (27, 0, 12.5), 4.2, 2.0), "beak", blend=1.5 * s, part="head"),
    ]
    for side, (forward, out, up) in ((-1, (0.38, 0.86, 0.26)), (1, (0.37, 0.87, 0.24))):
        look = np.array([forward, side * out, up])
        look /= np.linalg.norm(look)
        white = np.array(head) + look * 14.2
        # The pupil sits a little forward on the white, so she looks ahead, not sideways.
        pupil = np.array(head) + look * 16.6 + np.array([1.6, 0, 0.3])
        pieces.append(Piece(disc(white * s, 8.6 * s, 2.6 * s, look), "eye", 1.2 * s, "head"))
        pieces.append(Piece(disc(pupil * s, 4.6 * s, 1.8 * s, look), "pupil", 0.6 * s, "head"))
    return Figure(
        tuple(pieces),
        CLAYS,
        lump_height=0.65 * s,
        lump_size=8 * s,
        seam_depth=0.5 * s,
        seam_width=0.7 * s,
        mottle=0.065,
        mottle_size=6 * s,
        seed=7,
    )


def _scaled(v, s: float) -> tuple[float, float, float]:
    x, y, z = v
    return x * s, y * s, z * s
