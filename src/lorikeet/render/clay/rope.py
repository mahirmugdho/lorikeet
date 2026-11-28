"""A rope of dark clay laid round each stuck-down note.

It's the clay set's answer to the pencil line the flat and sketch looks draw round a note
(`render.pencil.around`): it shows the player the note counts. It's dark, like the pencil:
it sits just outside the paper, and dark clay adds no light or colour to the paper next to
it, which would change the note's colour for the camera.

Unlike the figures, a rope isn't meshed from distances: it's built directly, as a tube swept
along the note's outline. Every note has its own outline and turns up mid-game, and a tube
takes well under a millisecond to build with numpy, so a new note never stalls a frame. It
still gets the clay treatment: it's rolled by hand, so it's a little thicker and thinner
along its length and doesn't lie quite flat, and the clay shader boils it like any figure.
"""

from __future__ import annotations

import math

import numpy as np

from lorikeet.render.clay.colour import linear
from lorikeet.render.clay.figure import MAX_CLAYS, MAX_PARTS, ClayMesh
from lorikeet.render.clay.shapes import Lumps, inset
from lorikeet.render.pencil import NOTE_GAP

ROPE = (70, 60, 52)
"""A dark, warm clay."""

THICKNESS = 3.5
"""The rope's radius, in pixels."""

ALONG, AROUND = 1.5, 10
"""Pixels between rings of vertices along the rope, and vertices round each ring."""

ROUND_CORNERS = 3
"""Rounds of corner cutting: each round cuts every corner, so three give a corner about as
round as a rope laid round a square would bend."""


def rope(outline: tuple[tuple[float, float], ...], seed: int = 0) -> ClayMesh:
    """A rope round `outline` (projector pixels round the note's centre), its inner edge
    `NOTE_GAP` outside the paper, at the play layer (depth 0)."""
    # The rope's middle runs one rope's radius further out than the gap, every edge moved
    # out exactly that far.
    path = _path(inset(np.array(outline, dtype=np.float64), -(NOTE_GAP + THICKNESS)))
    rng = np.random.default_rng(seed)
    n = len(path)
    s = np.arange(n) * ALONG  # how far along the rope each ring is
    # Laid by hand: the rope drifts a little in and out, and towards and away from the wall,
    # and it's thicker and thinner along its length.
    drift, lift, thick = (_wave(s, rng, 0.6), _wave(s, rng, 0.8), _wave(s, rng, 0.14))

    tangent = np.roll(path, -1, axis=0) - np.roll(path, 1, axis=0)
    tangent /= np.linalg.norm(tangent, axis=1, keepdims=True)
    # Outwards, in the wall's plane: the tangent turned a quarter. Which way is outwards
    # depends on which way round the outline runs.
    side = np.stack([tangent[:, 1], -tangent[:, 0]], axis=1)
    centre = path.mean(axis=0)
    if np.einsum("ij,ij->", side, path - centre) < 0:
        side = -side
    flat = path + side * drift[:, None]

    # To the set: projector x is world x, projector y is down so world z is -y, and depth
    # is world y, with the camera at -y.
    middle = np.stack([flat[:, 0], lift, -flat[:, 1]], axis=1)
    outwards = np.stack([side[:, 0], np.zeros(n), -side[:, 1]], axis=1)
    towards_camera = np.array([0.0, -1.0, 0.0])
    angle = np.linspace(0, math.tau, AROUND, endpoint=False)
    radial = (
        np.cos(angle)[None, :, None] * outwards[:, None, :]
        + np.sin(angle)[None, :, None] * towards_camera[None, None, :]
    )
    radius = THICKNESS * (1 + thick)
    positions = (middle[:, None, :] + radius[:, None, None] * radial).reshape(-1, 3)

    normals = _grid_normals(positions.reshape(n, AROUND, 3), radial)
    triangles = _tube_triangles(n, AROUND, positions, normals)
    count = len(positions)
    # A rope on the wall is a little darker on the side facing the wall, which sees less of
    # the room's light.
    occlusion = np.clip(0.85 - 0.3 * normals[:, 1], 0.5, 1.0)
    distances = np.full((count, MAX_CLAYS), 10.0, dtype=np.float32)
    distances[:, 0] = -1.0
    palette = np.zeros((MAX_CLAYS, 3), dtype=np.float32)
    palette[0] = linear(ROPE)
    tint = 1 + 0.06 * Lumps(seed + 31, 8.0, 1.0)(positions.astype(np.float32))
    weights = np.zeros((count, MAX_PARTS), dtype=np.float32)
    weights[:, 0] = 1.0
    return ClayMesh(
        positions.astype(np.float32),
        normals.astype(np.float32),
        occlusion.astype(np.float32),
        triangles,
        distances,
        palette,
        np.repeat(tint[:, None], 3, axis=1).astype(np.float32),
        weights,
    )


def _path(outline: np.ndarray) -> np.ndarray:
    """The closed outline with its corners rounded off, as points `ALONG` pixels apart."""
    points = outline
    # Cut each edge into short pieces first, so rounding only touches the corners.
    pieces = []
    for a, b in zip(points, np.roll(points, -1, axis=0), strict=True):
        steps = max(1, math.ceil(np.linalg.norm(b - a) / 8.0))
        pieces.append(a + (b - a) * (np.arange(steps) / steps)[:, None])
    path = np.concatenate(pieces)
    for _ in range(ROUND_CORNERS):  # Chaikin's corner cutting
        after = np.roll(path, -1, axis=0)
        path = np.stack([0.75 * path + 0.25 * after, 0.25 * path + 0.75 * after], 1).reshape(-1, 2)
    # Even spacing, so the rope's lumps and the mesh are the same all the way round.
    step = np.linalg.norm(np.roll(path, -1, axis=0) - path, axis=1)
    run = np.concatenate([[0.0], np.cumsum(step)])
    total = run[-1]
    wanted = np.arange(0.0, total, total / max(8, round(total / ALONG)))
    closed = np.vstack([path, path[:1]])
    return np.stack([np.interp(wanted, run, closed[:, i]) for i in (0, 1)], axis=1)


def _wave(s: np.ndarray, rng: np.random.Generator, size: float) -> np.ndarray:
    """A slow, uneven wobble along the rope, about `size` either way. The wavelengths fit the
    rope's length exactly, so it closes up with no step where its ends meet."""
    total = s[-1] + (s[1] - s[0] if len(s) > 1 else 1.0)
    wobble = np.zeros_like(s)
    for wavelength, share in ((60.0, 0.6), (31.0, 0.3), (17.0, 0.15)):
        turns = max(1, round(total / wavelength))
        wobble += share * np.sin(math.tau * turns * s / total + rng.uniform(0, math.tau))
    return size * wobble


def _grid_normals(grid: np.ndarray, radial: np.ndarray) -> np.ndarray:
    """Normals from the vertices themselves (so the lumps shade), facing out of the tube."""
    along = np.roll(grid, -1, axis=0) - np.roll(grid, 1, axis=0)
    round_ = np.roll(grid, -1, axis=1) - np.roll(grid, 1, axis=1)
    normal = np.cross(along, round_)
    normal *= np.sign(np.einsum("ijk,ijk->ij", normal, radial))[..., None]
    normal /= np.linalg.norm(normal, axis=2, keepdims=True)
    return normal.reshape(-1, 3)


def _tube_triangles(n: int, m: int, positions: np.ndarray, normals: np.ndarray) -> np.ndarray:
    """Two triangles per square of the grid, closed all the way round both ways, wound to
    face out (back faces aren't drawn, so a tube wound inwards would be invisible). The grid
    runs the same way everywhere, so they all face the same way: the majority decides."""
    i, j = np.meshgrid(np.arange(n), np.arange(m), indexing="ij")
    a = (i * m + j).ravel()
    b = (i * m + (j + 1) % m).ravel()
    c = (((i + 1) % n) * m + (j + 1) % m).ravel()
    d = (((i + 1) % n) * m + j).ravel()
    triangles = np.concatenate([np.stack([a, b, c], 1), np.stack([a, c, d], 1)])
    p = positions[triangles]
    facing = np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0])
    inwards = np.einsum("ij,ij->i", facing, normals[triangles].sum(axis=1)) < 0
    if inwards.mean() > 0.5:
        triangles = triangles[:, ::-1]
    return np.ascontiguousarray(triangles, dtype=np.uint32)
