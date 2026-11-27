"""Clay recipes for the rest of Nest's things: ledges, the nest, the egg, the blossom and the
go ring. First drafts, made the same way as Lori (`lori.py`): pieces of clay pressed
together, so they live in the same clay world.

Each recipe takes the size the game gives the thing (a circle's radius, a ledge's outline)
and works in pixels, with x right, y away from the camera and z up, around the thing's own
centre.

Colours: these are the game's own things, so detection ignores colours inside them (issue
#12), but the big, flat ledges are kept muted anyway: they cover a lot of the wall, and a
real note can sit right against one.
"""

from __future__ import annotations

import math

import numpy as np

from lorikeet.render.clay.figure import Figure, Piece
from lorikeet.render.clay.shapes import Ellipsoid, Scaled, Slab, Torus, disc, rotation

LEDGE = (150, 140, 126)
"""A muted, sandy stone clay: about 16% saturated, a long way under a note's."""


def ledge(outline: tuple[tuple[float, float], ...], back: float) -> Figure:
    """A slab of rolled-out clay cut to `outline` (projector pixels around the ledge's
    centre), from 30 px in front of the play layer back to `back`, where it meets the
    backdrop, like a shelf. Its top edge is exactly where the physics has it; the edges
    are rounded inside the outline and the whole slab is gently uneven."""
    xz = tuple((x, -y) for x, y in outline)  # projector y is down; world z is up
    return Figure(
        (Piece(Slab(xz, front=-30.0, back=back, round=7.0), "ledge"),),
        {"ledge": LEDGE},
        lump_height=1.0,
        lump_size=26.0,
        mottle=0.05,
        mottle_size=18.0,
        reach=4.0,
        seed=11,
    )


def nest(radius: float) -> Figure:
    """A coil pot: a rope of brown clay coiled into a bowl, wider at the top, sitting on
    the ground at the bottom of the nest's circle. Each coil is a ring, squashed front to
    back so the nest isn't deeper than the shelf it sits on, pressed lightly onto the one
    below, so the creases between coils stay."""
    r = radius
    tube = 0.17 * r
    coils = ((0.78, -0.86), (1.0, -0.62), (1.17, -0.36), (1.28, -0.1))
    pieces = [Piece(Ellipsoid((0, 0, -0.84 * r), (0.8 * r, 0.4 * r, 0.16 * r)), "nest")]
    for i, (across, height) in enumerate(coils):
        # Each coil is a touch off-centre and tipped, as if coiled by hand.
        wobble = rotation(pitch=2.0 * math.sin(i * 2.1), roll=3.0 * math.cos(i * 1.7))
        ring = Torus((0.02 * r * math.sin(i * 1.3), 0, height * r), across * r, tube, wobble)
        pieces.append(Piece(Scaled(ring, (1.0, 0.5, 1.0)), "nest", blend=0.06 * r))
    return Figure(
        tuple(pieces),
        {"nest": (124, 90, 62)},
        lump_height=0.5,
        lump_size=8.0,
        seam_depth=0.0,
        mottle=0.07,
        mottle_size=7.0,
        seed=5,
    )


def egg(radius: float) -> Figure:
    """Smooth pale clay, a little narrower at the top, with a few speckles of darker clay
    pressed in. Nearly round, because the game rolls it as a ball."""
    r = radius
    pieces = [
        Piece(Ellipsoid((0, 0, -0.05 * r), (0.98 * r, 0.92 * r, 0.95 * r)), "shell"),
        Piece(Ellipsoid((0, 0, 0.26 * r), (0.7 * r, 0.68 * r, 0.68 * r)), "shell", 0.4 * r),
    ]
    rng = np.random.default_rng(3)
    for _ in range(9):
        # Speckles on the side towards the camera (-y), where they'll be seen.
        d = rng.normal(size=3) * [1, 0.5, 1] + [0, -1.2, 0]
        d /= np.linalg.norm(d)
        size = rng.uniform(0.06, 0.11) * r
        at = d * 0.93 * r
        pieces.append(Piece(disc(at, size, 0.04 * r, d), "speckle", 0.02 * r))
    return Figure(
        tuple(pieces),
        {"shell": (238, 230, 212), "speckle": (168, 138, 108)},
        lump_height=0.25,
        lump_size=10.0,
        seam_depth=0.15,
        seam_width=0.4,
        mottle=0.035,
        mottle_size=9.0,
        seed=2,
    )


def blossom(radius: float) -> Figure:
    """Soft clay petals round a yellow centre, the flower facing the camera."""
    r = radius
    pieces = [Piece(Ellipsoid((0, 0, 0), (0.36 * r, 0.3 * r, 0.36 * r)), "centre")]
    for k in range(6):
        a = math.radians(k * 60 + 15)
        at = (0.58 * r * math.cos(a), 0.06 * r, 0.58 * r * math.sin(a))
        # Each petal lies along its own direction out from the centre.
        petal = Ellipsoid(at, (0.46 * r, 0.16 * r, 0.3 * r), rotation(pitch=math.degrees(a)))
        pieces.append(Piece(petal, "petal", blend=0.08 * r))
    pieces.append(pieces.pop(0))  # the centre last: pressed on top of the petals
    return Figure(
        tuple(pieces),
        {"petal": (236, 146, 168), "centre": (244, 200, 74)},
        lump_height=0.4,
        lump_size=7.0,
        seam_depth=0.35,
        seam_width=0.5,
        mottle=0.05,
        mottle_size=6.0,
        seed=9,
    )


def go_ring(radius: float) -> Figure:
    """A plain grey clay ring, facing the camera, empty in the middle (the note goes
    there, and light under a note would change its colour for the camera)."""
    tube = 6.0
    ring = Torus((0, 0, 0), radius - tube, tube, rotation(roll=90))
    return Figure(
        (Piece(ring, "ring"),),
        {"ring": (140, 138, 134)},
        lump_height=0.6,
        lump_size=12.0,
        mottle=0.05,
        mottle_size=10.0,
        seed=4,
    )
