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

import itertools
import math

import numpy as np

from lorikeet.render.clay.figure import Figure, Piece
from lorikeet.render.clay.shapes import (
    Coil,
    Coin,
    Cracked,
    Egg,
    Ellipsoid,
    Placed,
    RoundCone,
    Shell,
    Slab,
    Torus,
    disc,
    egg_parts,
    rotation,
    smooth_union,
)

LEDGE = (164, 150, 130)
"""A warm, sandy clay, kept muted: about 28% saturated on screen, a long way under a
note's."""

LEDGE_FRONT = -40.0
"""How far in front of the play layer a ledge's front face is, in pixels: far enough that
everything resting on a ledge (Lori's nest, the egg) stands on its top, not over its edge."""


def ledge(outline: tuple[tuple[float, float], ...], back: float) -> Figure:
    """A slab of rolled-out clay cut to `outline` (projector pixels around the ledge's
    centre), from `LEDGE_FRONT` back to `back`, where it meets the backdrop, like a shelf.
    Its top edge is exactly where the physics has it; the edges are rounded inside the
    outline and the whole slab is gently uneven."""
    xz = tuple((x, -y) for x, y in outline)  # projector y is down; world z is up
    return Figure(
        (Piece(Slab(xz, front=LEDGE_FRONT, back=back, round=7.0), "ledge"),),
        {"ledge": LEDGE},
        lump_height=1.0,
        lump_size=26.0,
        mottle=0.05,
        mottle_size=18.0,
        reach=4.0,
        seed=11,
    )


NEST_FRONT, NEST_BACK = 0.6, 0.3
"""How far the nest's bowl reaches towards the camera and away from it, as a share of how
far it reaches to each side."""


def nest(radius: float) -> Figure:
    """A coil pot for Lori to sit in: a rope of brown clay coiled into a bowl, wider at the
    top, sitting on the ground at the bottom of the nest's circle. Each coil is pressed
    lightly onto the one below, so the creases between coils stay.

    It's built like a stage set, for the camera. The camera looks straight at it, so only
    the bowl's front wall ever shows: the back of the rim hides behind the front of it, and
    Lori fills the middle. So the bowl is deep in front, to stand well clear of her, and
    shallow behind, where it only has to fit in front of the backdrop."""
    r = radius
    tube = 0.16 * r
    coils = ((0.8, -0.84), (1.04, -0.6), (1.24, -0.34), (1.4, -0.08))
    floor_front, floor_back = NEST_FRONT * 0.8 * r, NEST_BACK * 0.8 * r
    pieces = [
        Piece(
            Ellipsoid(
                (0, (floor_back - floor_front) / 2, -0.84 * r),
                (0.8 * r, (floor_front + floor_back) / 2, tube),
            ),
            "nest",
        )
    ]
    for i, (across, height) in enumerate(coils):
        # Each coil is a touch off-centre, tipped and thicker or thinner, as if by hand.
        wobble = rotation(pitch=2.0 * math.sin(i * 2.1), roll=3.0 * math.cos(i * 1.7))
        a = across * r
        coil = Coil(
            (0.02 * r * math.sin(i * 1.3), 0, height * r),
            across=a,
            front=NEST_FRONT * a,
            back=NEST_BACK * a,
            tube=tube * (1 + 0.08 * math.sin(i * 2.7)),
            turn=wobble,
        )
        pieces.append(Piece(coil, "nest", blend=0.06 * r))
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


EGG_SHELL, EGG_SPECKLE = (238, 228, 208), (160, 128, 98)


def egg(radius: float) -> Figure:
    """A hen's egg in pale clay: wider below and narrower above, about a quarter taller than
    it's wide, with darker speckles pressed in. Rolled between the palms, so it's a little
    lumpy and dented, not a perfect shell.

    The game rolls it as a ball of `radius`, and the egg is drawn about that size, its long
    axis along z (up, before the game turns it). As it rolls, the clay set lifts or lowers
    it a little so its lowest point stays where the ball's is (`scene.py`)."""
    r = radius
    bottom, top, blend = egg_parts(r)
    pieces = [Piece(bottom, "shell"), Piece(top, "shell", blend=blend)]
    for speckle in _speckles(r):
        pieces.append(Piece(speckle, "speckle", 0.02 * r))
    return Figure(
        tuple(pieces),
        {"shell": EGG_SHELL, "speckle": EGG_SPECKLE},
        lump_height=0.5,
        lump_size=9.0,
        seam_depth=0.15,
        seam_width=0.4,
        mottle=0.06,
        mottle_size=8.0,
        seed=2,
    )


def _speckles(r: float) -> list[Ellipsoid]:
    """The egg's speckles: small discs pressed into its shell on the side the camera sees
    (-y; the egg only turns in the wall's plane). The same every time, so a broken egg's
    halves have the speckles the whole egg had."""
    bottom, top, blend = egg_parts(r)
    rng = np.random.default_rng(3)
    speckles = []
    for _ in range(11):
        d = rng.normal(size=3) * [1, 0.45, 1.25] + [0, -1.1, 0]
        d /= np.linalg.norm(d)
        size = rng.uniform(0.05, 0.1) * r
        speckles.append(disc(_onto_egg(bottom, top, blend, d), size, 0.035 * r, d))
    return speckles


def _onto_egg(bottom: Ellipsoid, top: Ellipsoid, blend: float, direction) -> np.ndarray:
    """Where a ray from the egg's middle along `direction` meets its surface."""
    near, far = 0.0, 2.0 * max(bottom.radii)
    for _ in range(40):  # halve the gap until it's far below a pixel
        mid = (near + far) / 2
        p = np.array([direction], dtype=np.float32) * mid
        inside = smooth_union(bottom.distance(p), top.distance(p), blend)[0] < 0
        near, far = (mid, far) if inside else (near, mid)
    return np.asarray(direction) * near


EGG_WHITE, YOLK = (246, 242, 230), (222, 196, 148)
"""A broken egg's puddle. The yolk is muted, well short of a yellow note's colour, so the
camera never takes it for one."""


def broken_egg(radius: float) -> Figure:
    """The egg after it lands on the floor: its shell (hollow, now you can see it) cracked
    round the middle along a zigzag, the bottom half still standing where the egg was, the
    top half tipped over on its side to the right, and a little puddle of egg round them on
    the ground (the bottom of the egg's circle). Swapped in for the egg as it breaks."""
    r = radius
    shell = Shell(Egg(r), thickness=0.12 * r)
    crack = {"height": 0.04 * r, "teeth": 7, "depth": 0.13 * r}
    bottom = Cracked(shell, **crack)
    # Tipped over: its dome turned to point right and a touch down, resting on the ground.
    tipped = {"at": (1.3 * r, 0.0, -0.1 * r), "turn": rotation(pitch=-100)}
    top = Placed(Cracked(shell, above=True, **crack), **tipped)
    pieces = [
        Piece(Ellipsoid((0.3 * r, -0.05 * r, -r), (1.5 * r, 0.5 * r, 0.08 * r)), "white"),
        Piece(
            Ellipsoid((0.75 * r, -0.2 * r, -0.94 * r), (0.32 * r, 0.26 * r, 0.13 * r)),
            "yolk",
            blend=0.04 * r,
        ),
        Piece(bottom, "shell", blend=0.03 * r),
        Piece(top, "shell", blend=0.03 * r),
    ]
    # The whole egg's speckles, each on the half it was on (clear of the crack's zigzag).
    for speckle in _speckles(r):
        height = speckle.centre[2]
        if height < crack["height"] - crack["depth"] - 0.05 * r:
            pieces.append(Piece(speckle, "speckle", 0.02 * r))
        elif height > crack["height"] + crack["depth"] + 0.05 * r:
            pieces.append(Piece(Placed(speckle, **tipped), "speckle", 0.02 * r))
    return Figure(
        tuple(pieces),
        {"white": EGG_WHITE, "yolk": YOLK, "shell": EGG_SHELL, "speckle": EGG_SPECKLE},
        lump_height=0.4,
        lump_size=9.0,
        seam_depth=0.2,
        seam_width=0.4,
        mottle=0.05,
        mottle_size=8.0,
        seed=2,
    )


GO_DISC, GO_LETTERS = (152, 144, 132), (76, 66, 58)
"""A warm grey round of clay, with "go" in dark clay: dark adds no light or colour to the
go note, which covers the middle of the disc."""

GO_THICKNESS = 8.0
"""The go disc's thickness, in pixels."""


def go_disc(radius: float) -> Figure:
    """The go spot: a round of clay pressed flat onto the wall, filling the spot's circle,
    with "go" written across it in thin rolled clay, the way you'd letter a clay sign. The
    go note goes on top of it, covering the word, which is the point: it says where the
    note goes until there's one there."""
    r = radius
    face = -GO_THICKNESS / 2  # the disc's front, towards the camera
    pieces = [Piece(Coin((0, 0, 0), r, GO_THICKNESS, round=3.0), "disc")]
    rope = 0.05 * r  # the letters' thickness
    y = face - 0.5 * rope  # half sunk into the face, as if pressed on
    bowl, middle = 0.19 * r, 0.1 * r  # the letters' round parts: radius, and height
    facing = rotation(roll=90)  # a ring whose axis looks along y, at the camera
    g, o = -0.25 * r, 0.25 * r  # where each letter's bowl is, across
    pieces.append(Piece(Torus((o, y, middle), bowl, rope, facing), "letters", 0.4 * rope))
    pieces.append(Piece(Torus((g, y, middle), bowl, rope, facing), "letters", 0.4 * rope))
    # The g's tail: down the right of its bowl, then an open hook curling back to the left
    # underneath, as a handwritten g's does.
    stem_x = g + bowl
    path = [(stem_x, middle + 0.7 * bowl), (stem_x, middle - 1.4 * bowl)]
    hook_centre, hook = (g + 0.05 * bowl, middle - 1.4 * bowl), 0.95 * bowl
    for degrees in range(-10, -171, -20):
        a = math.radians(degrees)
        path.append((hook_centre[0] + hook * math.cos(a), hook_centre[1] + hook * math.sin(a)))
    for (x0, z0), (x1, z1) in itertools.pairwise(path):
        piece = RoundCone((x0, y, z0), (x1, y, z1), rope, rope)
        pieces.append(Piece(piece, "letters", 0.4 * rope))
    return Figure(
        tuple(pieces),
        {"disc": GO_DISC, "letters": GO_LETTERS},
        lump_height=0.6,
        lump_size=12.0,
        seam_depth=0.3,
        seam_width=0.6,
        mottle=0.05,
        mottle_size=10.0,
        seed=4,
    )


# The flower bed: leaves, stems and flower heads are separate figures, so the clay set can
# grow the stems and swap each flower for a more open one, frame by frame, the way stop-
# motion animators replace pieces (`bed.py` lays the bed out and times the bloom).

LEAF_GREENS = ((58, 140, 64), (44, 116, 56))
STEM_GREEN = (64, 138, 66)
FLOWER_STAGES = 4
"""How many flower heads there are, from a closed bud (0) to wide open (3)."""


def bed_leaves(radius: float) -> Figure:
    """The bed's mound of leaves: broad clay leaves fanned out along the ground, overlapping,
    a little wider than the bed's circle. The ground is at the bottom of the circle."""
    r = radius
    ground = -r
    rng = np.random.default_rng(12)
    pieces = []
    for k in range(9):
        across = (k / 8 - 0.5) * 2.2 * r + rng.uniform(-0.06, 0.06) * r
        lean = across / r * 32 + rng.uniform(-12, 12)  # leaning outwards, more at the sides
        length = rng.uniform(0.46, 0.62) * r
        # A leaf: long, flat and pointed, standing up out of the ground and leaning out.
        turn = rotation(pitch=90 - lean, heading=rng.uniform(-25, 25))
        centre = (
            across + math.sin(math.radians(lean)) * 0.5 * length,
            rng.uniform(-6, 6),
            ground + math.cos(math.radians(lean)) * 0.45 * length,
        )
        leaf = Ellipsoid(centre, (length * 0.6, 0.05 * r, 0.16 * r), turn)
        pieces.append(Piece(leaf, f"leaf {k % 2}", blend=0.05 * r))
    pieces.append(Piece(Ellipsoid((0, 0, ground), (1.1 * r, 0.3 * r, 0.12 * r)), "leaf 1", 0.1 * r))
    return Figure(
        tuple(pieces),
        {"leaf 0": LEAF_GREENS[0], "leaf 1": LEAF_GREENS[1]},
        lump_height=0.4,
        lump_size=6.0,
        seam_depth=0.3,
        seam_width=0.5,
        mottle=0.06,
        mottle_size=6.0,
        seed=12,
    )


def stem(length: float) -> Figure:
    """A thin green stem standing up from its foot at the origin, with a small leaf on it.
    The clay set stretches it upwards to grow it."""
    pieces = [
        Piece(RoundCone((0, 0, 0), (0, 0, length), 2.6, 1.9), "stem"),
        Piece(
            Ellipsoid((3.5, -1, 0.4 * length), (5.0, 1.2, 2.2), rotation(pitch=35)),
            "stem",
            blend=1.5,
        ),
    ]
    return Figure(tuple(pieces), {"stem": STEM_GREEN}, lump_height=0.2, lump_size=5.0, seed=13)


def flower_head(size: float, stage: int) -> Figure:
    """One clay flower facing the camera: six petals round a round centre, `size` across
    its petals when open. `stage` opens it, from 0 (a closed bud, its petals folded forward
    round the centre) to `FLOWER_STAGES - 1` (wide open, flat). Its clays are "petal" then
    "centre", in that order, so the clay set can recolour each flower in the bed."""
    opening = stage / (FLOWER_STAGES - 1)
    fold = math.radians(72 * (1 - opening))  # how far the petals fold forward, at the camera
    length = size * (0.3 + 0.2 * opening)
    pieces = []
    for k in range(6):
        a = math.radians(60 * k + 15)
        out = np.array([math.cos(a), 0.0, math.sin(a)])
        # Along the petal: outwards, folded forward towards the camera (-y).
        along = out * math.cos(fold) + np.array([0.0, -math.sin(fold), 0.0])
        across = np.array([-math.sin(a), 0.0, math.cos(a)])
        facing = np.cross(across, along)
        turn = np.stack([along, facing, across], axis=1).astype(np.float32)
        centre = along * (0.55 * length + 0.08 * size)
        petal = Ellipsoid(tuple(centre), (0.55 * length, 0.07 * size, 0.2 * size), turn)
        pieces.append(Piece(petal, "petal", blend=0.05 * size))
    heart = 0.16 * size * (0.85 + 0.15 * opening)
    pieces.append(Piece(Ellipsoid((0, -0.04 * size, 0), (heart, 0.8 * heart, heart)), "centre"))
    return Figure(
        tuple(pieces),
        {"petal": (236, 140, 168), "centre": (244, 200, 74)},
        lump_height=0.25,
        lump_size=5.0,
        seam_depth=0.35,
        seam_width=0.5,
        mottle=0.05,
        mottle_size=5.0,
        seed=9 + stage,
    )
