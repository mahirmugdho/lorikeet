"""Turn a signed distance function into a smooth triangle mesh, once, at startup.

The method is *surface nets*, the simplest good one:

1. Sample the distance on a 3D grid of points `step` apart.
2. Every grid cell whose corners aren't all inside or all outside straddles the surface.
   Each such cell gets one vertex, at the average of the points where the surface crosses
   the cell's edges.
3. Every grid edge the surface crosses is surrounded by four such cells. Their four vertices
   make one quad (two triangles).

Then two steps make it look like clay instead of a 3D game:

- **On the true surface.** The averaged vertices sit slightly off the surface, which would
  show up as faint ripples in the shading. A few Newton steps slide each one onto the exact
  zero of the distance.
- **Smooth normals.** Each vertex's normal is the direction the distance grows fastest (its
  gradient), measured on the shape itself, not averaged from the triangles around it. So the
  shading is as smooth as the shape, whatever size the triangles are, and nothing looks
  faceted.

A grid fine enough for smooth silhouettes has millions of points, but only the few near the
surface matter. So the distance is first measured once per block of points, and blocks that
are clearly all inside or all outside are skipped (see `_sample`). That's what keeps building
a figure to a second or two.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np

Field = Callable[[np.ndarray], np.ndarray]
"""A signed distance function: points (n, 3) in, distances (n,) out."""

_CORNERS = np.array([(x, y, z) for z in (0, 1) for y in (0, 1) for x in (0, 1)])
_EDGES = [(a, b) for a in range(8) for b in range(8) if a < b and bin(a ^ b).count("1") == 1]
_BLOCK = 8  # points per block side, when skipping blocks far from the surface


@dataclass(frozen=True)
class Mesh:
    positions: np.ndarray
    """(n, 3) float32, on the surface."""
    normals: np.ndarray
    """(n, 3) float32, unit length, pointing out."""
    triangles: np.ndarray
    """(m, 3) uint32 indices into the vertices, wound counter-clockwise seen from outside."""


def mesh_field(
    field: Field, lower: tuple[float, ...], upper: tuple[float, ...], step: float
) -> Mesh:
    """Mesh the surface where `field` is zero, inside the box from `lower` to `upper`.

    The box must enclose the whole shape with some room to spare, or the mesh will have
    holes where the shape is cut off. `step` sets the grid spacing: the mesh has triangles
    about that size."""
    origin = np.asarray(lower, dtype=np.float64)
    shape = tuple(math.ceil((u - lo) / step) + 1 for lo, u in zip(lower, upper, strict=True))
    values = _sample(field, origin, step, shape)
    inside = values < 0

    # Which cells straddle the surface: some corners inside, some outside.
    nx, ny, nz = shape
    corner_inside = [inside[x : nx - 1 + x, y : ny - 1 + y, z : nz - 1 + z] for x, y, z in _CORNERS]
    count = np.sum(corner_inside, axis=0)
    straddles = (count > 0) & (count < 8)
    cells = np.argwhere(straddles)
    if len(cells) == 0:
        empty = np.zeros((0, 3), dtype=np.float32)
        return Mesh(empty, empty, np.zeros((0, 3), dtype=np.uint32))
    vertex_of = np.full(straddles.shape, -1, dtype=np.int64)
    vertex_of[straddles] = np.arange(len(cells))

    # One vertex per straddling cell, at the average of its edge crossings.
    corner_values = np.stack(
        [values[cells[:, 0] + x, cells[:, 1] + y, cells[:, 2] + z] for x, y, z in _CORNERS], axis=1
    )
    total = np.zeros((len(cells), 3))
    crossings = np.zeros(len(cells))
    for a, b in _EDGES:
        va, vb = corner_values[:, a], corner_values[:, b]
        crosses = (va < 0) != (vb < 0)
        with np.errstate(divide="ignore", invalid="ignore"):
            t = np.where(crosses, va / (va - vb), 0.0)
        point = _CORNERS[a] + t[:, None] * (_CORNERS[b] - _CORNERS[a])
        total += np.where(crosses[:, None], point, 0.0)
        crossings += crosses
    positions = origin + (cells + total / crossings[:, None]) * step

    triangles = _quads(inside, vertex_of, positions)
    positions = _onto_surface(field, positions, step)
    normals = _gradient(field, positions, step * 0.25)
    triangles = _face_outward(triangles, positions, normals)
    return Mesh(positions.astype(np.float32), normals.astype(np.float32), triangles)


def _sample(field: Field, origin: np.ndarray, step: float, shape: tuple[int, ...]) -> np.ndarray:
    """The distance at every grid point, measured exactly only near the surface.

    The grid is cut into blocks. Each block's distance is measured at its centre first. A
    distance can't change faster than the distance moved (that's what makes it a distance),
    so if the centre is further from the surface than the block's corners are from its
    centre, plus a safety margin, the whole block is on one side and every point in it gets
    the centre's value. Only the sign of those points matters to the mesher, and it's right."""
    blocks = [math.ceil(n / _BLOCK) for n in shape]
    index = np.indices(blocks).reshape(3, -1).T
    centres = origin + (index * _BLOCK + (_BLOCK - 1) / 2) * step
    centre_distance = field(centres.astype(np.float32))
    reach = (_BLOCK - 1) / 2 * step * math.sqrt(3)
    # 1.5x: the lumps and seams added to a figure's distance make it change a bit faster
    # than a true distance, so leave extra room. 2 steps: a point beside the surface must
    # be measured exactly, because its neighbour's crossing uses its value.
    near = np.abs(centre_distance) < 1.5 * reach + 2 * step

    padded = [b * _BLOCK for b in blocks]
    values = np.empty(padded, dtype=np.float32)
    far = index[~near]
    far_values = centre_distance[~near]
    for (bx, by, bz), v in zip(far, far_values, strict=True):
        values[
            bx * _BLOCK : (bx + 1) * _BLOCK,
            by * _BLOCK : (by + 1) * _BLOCK,
            bz * _BLOCK : (bz + 1) * _BLOCK,
        ] = v
    within = np.indices((_BLOCK,) * 3).reshape(3, -1).T
    near_points = (index[near][:, None, :] * _BLOCK + within[None, :, :]).reshape(-1, 3)
    values[near_points[:, 0], near_points[:, 1], near_points[:, 2]] = field(
        (origin + near_points * step).astype(np.float32)
    )
    return values[: shape[0], : shape[1], : shape[2]]


def _quads(inside: np.ndarray, vertex_of: np.ndarray, positions: np.ndarray) -> np.ndarray:
    """Two triangles for every grid edge the surface crosses, from the four cells around it."""
    nx, ny, nz = inside.shape
    found = []
    for axis in range(3):
        # The grid edges along this axis, leaving out the grid's outer faces, where an edge
        # doesn't have four cells around it.
        lo = [1, 1, 1]
        lo[axis] = 0
        hi = [nx - 1, ny - 1, nz - 1]
        here = inside[lo[0] : hi[0], lo[1] : hi[1], lo[2] : hi[2]]
        step = [0, 0, 0]
        step[axis] = 1
        there = inside[
            lo[0] + step[0] : hi[0] + step[0],
            lo[1] + step[1] : hi[1] + step[1],
            lo[2] + step[2] : hi[2] + step[2],
        ]
        edges = np.argwhere(here != there) + lo
        # The four cells around an edge differ in the two other axes by 0 or -1.
        u, v = [a for a in range(3) if a != axis]
        around = []
        for du, dv in ((-1, -1), (0, -1), (0, 0), (-1, 0)):
            cell = edges.copy()
            cell[:, u] += du
            cell[:, v] += dv
            around.append(vertex_of[cell[:, 0], cell[:, 1], cell[:, 2]])
        found.append(np.stack(around, axis=1))
    quads = np.concatenate(found)
    # Split each quad along its shorter diagonal: it bends the surface less.
    a, b, c, d = (positions[quads[:, i]] for i in range(4))
    across_ac = np.linalg.norm(a - c, axis=1) <= np.linalg.norm(b - d, axis=1)
    first = np.where(across_ac[:, None], quads[:, [0, 1, 2]], quads[:, [0, 1, 3]])
    second = np.where(across_ac[:, None], quads[:, [0, 2, 3]], quads[:, [1, 2, 3]])
    return np.concatenate([first, second]).astype(np.uint32)


def _onto_surface(field: Field, positions: np.ndarray, step: float) -> np.ndarray:
    """Slide each vertex onto the surface with Newton's method: move against the gradient by
    the distance, so a point 0.1 outside moves 0.1 inward. Three steps are plenty."""
    p = positions.copy()
    for _ in range(3):
        d = field(p.astype(np.float32)).astype(np.float64)
        g = _gradient(field, p, step * 0.25, normalise=False)
        squared = np.maximum(np.sum(g * g, axis=1), 1e-12)
        move = (d / squared)[:, None] * g
        # Never further than half a cell, so a vertex can't jump across a thin piece.
        length = np.linalg.norm(move, axis=1, keepdims=True)
        move *= np.minimum(1.0, 0.5 * step / np.maximum(length, 1e-12))
        p -= move
    return p


def _gradient(field: Field, p: np.ndarray, h: float, normalise: bool = True) -> np.ndarray:
    """The distance's gradient by central differences: the way out of the surface."""
    g = np.zeros_like(p, dtype=np.float64)
    for axis in range(3):
        offset = np.zeros(3)
        offset[axis] = h
        ahead = field((p + offset).astype(np.float32)).astype(np.float64)
        behind = field((p - offset).astype(np.float32)).astype(np.float64)
        g[:, axis] = (ahead - behind) / (2 * h)
    if normalise:
        g /= np.maximum(np.linalg.norm(g, axis=1, keepdims=True), 1e-12)
    return g


def _face_outward(triangles: np.ndarray, positions: np.ndarray, normals: np.ndarray) -> np.ndarray:
    """Wind every triangle counter-clockwise seen from outside, the way Panda3D expects, by
    flipping any whose face points against its vertices' normals."""
    a, b, c = (positions[triangles[:, i]] for i in range(3))
    facing = np.cross(b - a, c - a)
    outward = normals[triangles].sum(axis=1)
    backwards = np.einsum("ij,ij->i", facing, outward) < 0
    fixed = triangles.copy()
    fixed[backwards] = fixed[backwards][:, [0, 2, 1]]
    return fixed
