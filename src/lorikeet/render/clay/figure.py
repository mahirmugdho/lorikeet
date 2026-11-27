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
    """(n, 3) float32: multiplies the clay's colour per vertex. White on figures; the
    backdrop uses it for its gradient."""


def build(figure: Figure, step: float) -> ClayMesh:
    """Mesh the figure with triangles about `step` pixels across, work out its clays and
    bake its occlusion."""
    names = figure.clay_names
    if len(names) > MAX_CLAYS:
        raise ValueError(f"a figure can use at most {MAX_CLAYS} clays, not {len(names)}")
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
    tint = np.ones((len(mesh.positions), 3), dtype=np.float32)
    return ClayMesh(
        mesh.positions, mesh.normals, occlusion, mesh.triangles, distances, palette, tint
    )


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
