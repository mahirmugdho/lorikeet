"""A clay figure: pieces of coloured clay pressed together, built once into a mesh.

A `Figure` is a recipe: a list of `Piece`s, each a soft shape in one clay colour, and how
softly it's pressed onto what's already there. `build` turns the recipe into a `ClayMesh`
the renderer can draw: smooth vertices and normals (from `mesher.py`), and per vertex how
far it is from each clay and how much light reaches it (ambient occlusion).

What makes it read as handmade clay, and where each part happens:

- **Pressed-together joins.** Each piece is added with a smooth union, so the join is a
  soft neck, as if smoothed with a thumb (`shapes.smooth_union`).
- **One colour per piece.** Each pixel takes the colour of the clay it's nearest, so the
  colours meet in a clean line instead of fading into each other, the way two clays do
  (see `ClayMesh.clay_distances`).
- **A faint seam where two colours meet.** Where the surface is about equally near two
  different clays, it's pushed in a little, which makes a shallow groove along the join.
  The occlusion below then darkens it.
- **Lumps and dents.** A little smooth noise pushes the whole surface gently in and out
  (`shapes.Lumps`), so nothing is a perfect sphere.
- **Mottling.** Real plasticine is never one perfectly even colour: the pigment isn't quite
  evenly kneaded in, and handling leaves faintly lighter and darker patches. Each vertex's
  colour is nudged a few percent by smooth noise, baked in here so it costs nothing to draw.
- **Dark crevices.** Ambient occlusion, baked into each vertex: how boxed-in the surface is
  by the figure's own shape. Creases, seams and the gap under a wing come out darker, like
  soft studio light that can't quite reach in. The meshes never change shape, so it's done
  once here instead of every frame on the GPU (the brief rules out screen-space AO).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from functools import cached_property

import numpy as np

from lorikeet.render.clay.colour import linear
from lorikeet.render.clay.mesher import mesh_field
from lorikeet.render.clay.shapes import Lumps, Shape, smooth_union

RGB = tuple[int, int, int]


@dataclass(frozen=True)
class Piece:
    shape: Shape
    clay: str
    """Which clay it's made of: a key in the figure's `clays`."""
    blend: float = 0.0
    """How wide the soft neck is where it's pressed onto the pieces before it, in pixels.
    Big for parts of one body (a head on a body), small for things pressed on (eyes)."""
    part: str = ""
    """Which movable part it belongs to, for posing ("head", a wing). "" is the body."""


@dataclass(frozen=True)
class Figure:
    pieces: tuple[Piece, ...]
    clays: Mapping[str, RGB]
    """Each clay's colour, as sRGB 0-255, the way colours are usually written down."""
    lump_height: float = 0.0
    """How far the lumps push the surface in or out, in pixels."""
    lump_size: float = 10.0
    """How far apart the lumps are, in pixels."""
    seam_depth: float = 0.0
    """How deep the groove is where two clays meet, in pixels."""
    seam_width: float = 1.0
    """About how wide the groove is, in pixels."""
    seed: int = 0
    """Picks the lumps, so two figures from one recipe can differ."""
    mottle: float = 0.0
    """How much the colour wanders in faint patches: 0.05 is 5% lighter or darker."""
    mottle_size: float = 6.0
    """About how big the patches are, in pixels."""
    part_blend: float = 2.0
    """How far, in pixels, one part fades into the next where they join, so a turning head
    bends the neck like clay instead of tearing away from it."""
    reach: float = 6.0
    """How far from a piece its exact distance is still worked out, in pixels. Further out
    only a lower bound is used, which is all the mesher needs there: it only has to know
    the point is well outside. Most points are far from most pieces, so this makes
    building several times faster."""

    def __post_init__(self) -> None:
        unknown = {piece.clay for piece in self.pieces} - set(self.clays)
        if unknown:
            raise ValueError(f"pieces use clays with no colour: {sorted(unknown)}")

    def distance(self, p: np.ndarray) -> np.ndarray:
        """The whole figure's signed distance: pieces, seams and lumps together."""
        whole, nearest = self._pieces(p)
        if self.seam_depth > 0 and len(nearest) > 1:
            # The two nearest clays: where they're about equally near, the surface is at a
            # join between two colours.
            two = np.partition(nearest, 1, axis=0)[:2]
            gap = two[1] - two[0]
            whole = whole + self.seam_depth * np.exp(-((gap / self.seam_width) ** 2))
        if self.lump_height > 0:
            whole = whole + self._lumps(p)
        return whole.astype(np.float32)

    def clay_distances(self, p: np.ndarray) -> np.ndarray:
        """How far each point is from each clay: (clays, n), clays in `clay_names` order."""
        return self._pieces(p)[1]

    @property
    def part_names(self) -> list[str]:
        """The body first, then the movable parts in the order they first appear."""
        return ["", *dict.fromkeys(p.part for p in self.pieces if p.part)]

    def part_weights(self, p: np.ndarray) -> np.ndarray:
        """How much each part moves each point: (n, parts), each row adding up to 1.

        A point on the head is all head. Near where the head joins the body, both are
        about equally near, so it's half and half, and it fades smoothly between: each
        part's weight falls off exponentially with how much further away it is than the
        nearest part."""
        names = self.part_names
        nearest = np.full((len(names), len(p)), np.inf, dtype=np.float32)
        for piece in self.pieces:
            row = names.index(piece.part)
            nearest[row] = np.minimum(nearest[row], piece.shape.distance(p))
        further = nearest - nearest.min(axis=0)
        weights = np.exp(-further / self.part_blend)
        return (weights / weights.sum(axis=0)).T.astype(np.float32)

    @property
    def clay_names(self) -> list[str]:
        """The clays the pieces use, in the order they first appear."""
        return list(dict.fromkeys(piece.clay for piece in self.pieces))

    def bounds(self, margin: float) -> tuple[np.ndarray, np.ndarray]:
        lows, highs = zip(*(piece.shape.bounds() for piece in self.pieces), strict=True)
        room = margin + max(piece.blend for piece in self.pieces) + self.lump_height * 2
        return np.min(lows, axis=0) - room, np.max(highs, axis=0) + room

    def _pieces(self, p: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """The blended distance of all the pieces, and each clay's own nearest distance."""
        names = self.clay_names
        nearest = np.full((len(names), len(p)), np.inf, dtype=np.float32)
        whole: np.ndarray | None = None
        room = self.reach + max(piece.blend for piece in self.pieces) + 2 * self.lump_height
        for piece in self.pieces:
            # A point outside the piece's box grown by `room` is more than `room` from the
            # piece, so `room` is a safe stand-in for its distance.
            low, high = piece.shape.bounds()
            close = np.all((p > low - room) & (p < high + room), axis=1)
            d = np.full(len(p), room, dtype=np.float32)
            d[close] = piece.shape.distance(p[close])
            whole = d if whole is None else smooth_union(whole, d, piece.blend)
            row = names.index(piece.clay)
            nearest[row] = np.minimum(nearest[row], d)
        assert whole is not None  # a figure has at least one piece
        return whole, nearest

    @cached_property
    def _lumps(self) -> Lumps:
        return Lumps(self.seed, self.lump_size, self.lump_height)


MAX_CLAYS = 12
"""The most clays one figure can use: the shader gets each vertex's distance to every clay
in three groups of four."""

MAX_PARTS = 4
"""The most movable parts (counting the body) one figure can have: the shader gets each
vertex's weight for every part in one group of four."""


@dataclass(frozen=True)
class ClayMesh:
    positions: np.ndarray
    """(n, 3) float32, in pixels around the figure's own origin."""
    normals: np.ndarray
    """(n, 3) float32, unit length."""
    occlusion: np.ndarray
    """(n,) float32: 1 where the surface is open to the light, less in creases."""
    triangles: np.ndarray
    """(m, 3) uint32."""
    clay_distances: np.ndarray
    """(n, MAX_CLAYS) float32: how far each vertex is from each clay.

    The colour isn't decided per vertex, because then a line between two colours could
    only follow the triangles and would come out ragged. Instead the GPU blends these
    distances smoothly across each triangle, and every pixel takes the colour of the
    nearest clay. Distances change smoothly, so the line between two clays is a smooth
    curve however big the triangles are."""
    palette: np.ndarray
    """(MAX_CLAYS, 3) float32: each clay's colour in linear light (see `colour.py`)."""
    tint: np.ndarray
    """(n, 3) float32: multiplies the clay's colour per vertex: the mottling on figures,
    the gradient on the backdrop."""
    part_weights: np.ndarray
    """(n, MAX_PARTS) float32: how much each movable part moves each vertex (see
    `Figure.part_weights`). Column 0 is the body."""


@dataclass(frozen=True)
class Packed:
    """A mesh laid out as the graphics card takes it, ready to copy straight across."""

    rows: np.ndarray
    """(n, 26) float32, one row per vertex: position (3), normal (3), tint (3), occlusion
    (1), the distance to each clay (12) and each part's weight (4)."""
    triangles: np.ndarray
    """(m, 3) uint32."""
    palette: np.ndarray
    """(MAX_CLAYS, 3) float32, linear light."""


def pack(mesh: ClayMesh) -> Packed:
    """Lay a mesh out for the graphics card. It takes some milliseconds for a big figure,
    so the clay renderer does it while building, away from the game (see `builder.py`)."""
    rows = np.concatenate(
        [
            mesh.positions,
            mesh.normals,
            mesh.tint,
            mesh.occlusion[:, None],
            mesh.clay_distances,
            mesh.part_weights,
        ],
        axis=1,
    )
    return Packed(
        np.ascontiguousarray(rows, dtype=np.float32),
        np.ascontiguousarray(mesh.triangles, dtype=np.uint32),
        np.asarray(mesh.palette, dtype=np.float32),
    )


def build(figure: Figure, step: float) -> ClayMesh:
    """Mesh the figure with triangles about `step` pixels across, work out its clays and
    bake its occlusion."""
    names = figure.clay_names
    if len(names) > MAX_CLAYS:
        raise ValueError(f"a figure can use at most {MAX_CLAYS} clays, not {len(names)}")
    if len(figure.part_names) > MAX_PARTS:
        raise ValueError(f"a figure can have at most {MAX_PARTS} parts with its body")
    lower, upper = figure.bounds(margin=3 * step)
    mesh = mesh_field(figure.distance, tuple(lower), tuple(upper), step)
    palette = np.ones((MAX_CLAYS, 3), dtype=np.float32)
    palette[: len(names)] = [linear(figure.clays[name]) for name in names]
    # Far from a clay, only "far" matters; capping keeps the numbers small for the GPU.
    far = 10 * step
    distances = np.full((len(mesh.positions), MAX_CLAYS), far, dtype=np.float32)
    distances[:, : len(names)] = np.minimum(figure.clay_distances(mesh.positions).T, far)
    size = float(np.max(upper - lower))
    # Two reaches: a broad one for big hollows (under a wing, where a head meets a body),
    # and a short one that only sees tight creases, so seams get a crisp dark line.
    occlusion = occlusion_at(figure.distance, mesh.positions, mesh.normals, reach=size * 0.12)
    occlusion *= occlusion_at(figure.distance, mesh.positions, mesh.normals, reach=size * 0.025)
    tint = mottling(figure, mesh.positions)
    parts = np.zeros((len(mesh.positions), MAX_PARTS), dtype=np.float32)
    parts[:, : len(figure.part_names)] = figure.part_weights(mesh.positions)
    return ClayMesh(
        mesh.positions, mesh.normals, occlusion, mesh.triangles, distances, palette, tint, parts
    )


def mottling(figure: Figure, positions: np.ndarray) -> np.ndarray:
    """Each vertex's tint: 1, nudged by faint patches of lighter and darker clay.

    Mostly it's brightness (patches, plus smaller blotches at a third the size), with a
    smaller, separate wander in each of red, green and blue so the patches aren't pure
    grey; as in real clay, where the pigment is a little thicker in places."""
    tint = np.ones((len(positions), 3), dtype=np.float32)
    if figure.mottle <= 0:
        return tint
    size = figure.mottle_size
    seed = figure.seed + 101
    patches = Lumps(seed, size, 1.0)(positions) + 0.5 * Lumps(seed + 1, size / 3, 1.0)(positions)
    tint *= 1 + figure.mottle * 0.75 * patches[:, None]
    for channel in range(3):
        wander = Lumps(seed + 2 + channel, size, 1.0)(positions)
        tint[:, channel] *= 1 + figure.mottle * 0.3 * wander
    return tint.astype(np.float32)


def occlusion_at(
    field, positions: np.ndarray, normals: np.ndarray, reach: float, samples: int = 5
) -> np.ndarray:
    """How open each surface point is, from 1 (nothing nearby) down towards 0 (deep in a
    crease).

    The test steps straight out from the surface along the normal. On an open surface the
    distance to the shape grows exactly as fast as you step out. In a crease, other parts
    of the figure are nearby, so the distance grows more slowly. How much slower, summed
    over a few steps (nearer steps counting more), is how hidden the point is. This is
    Inigo Quilez's SDF ambient occlusion."""
    hidden = np.zeros(len(positions), dtype=np.float32)
    total = 0.0
    for i in range(1, samples + 1):
        out = reach * i / samples
        d = field((positions + normals * out).astype(np.float32))
        weight = 1.0 / i
        hidden += weight * np.clip((out - d) / out, 0.0, 1.0)
        total += weight
    # Never all the way to black: even a deep crease in clay catches some bounced light.
    return np.clip(1.0 - 1.6 * hidden / total, 0.2, 1.0).astype(np.float32)
