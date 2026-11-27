"""The soft shapes clay figures are modelled from, as signed distance functions.

A signed distance function (SDF) says, for any point, how far it is from a shape's surface:
negative inside, zero on the surface, positive outside. Modelling with them instead of with
triangles has two advantages that matter for the clay look:

- Shapes can be blended with a *smooth union* (`smooth_union`), which fills in the crease
  where two shapes meet with a rounded neck. That's what clay pressed into clay looks like,
  and it's very hard to get with separate meshes, which just intersect with a hard line.
- Imperfection is cheap: adding a little noise to the distance (`Lumps`) pushes the surface
  in and out, giving gentle lumps and dents, so no figure comes out as a perfect CG sphere.

The mesher (`mesher.py`) then turns the blended distance into a smooth triangle mesh once, at
startup. Everything here works on numpy arrays of points, shape (n, 3), so a whole grid of
points is evaluated at once.

Coordinates are Panda3D's: x right, y away from the camera (into the wall), z up.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Protocol

import numpy as np

Vec3 = tuple[float, float, float]
IDENTITY = np.eye(3, dtype=np.float32)


class Shape(Protocol):
    def distance(self, p: np.ndarray) -> np.ndarray:
        """Signed distance from each point in `p` (shape (n, 3)) to the surface."""
        ...

    def bounds(self) -> tuple[np.ndarray, np.ndarray]:
        """A box the shape fits inside: its lowest and highest corners."""
        ...


def rotation(heading: float = 0.0, pitch: float = 0.0, roll: float = 0.0) -> np.ndarray:
    """A rotation matrix from angles in degrees: `roll` about x, then `pitch` (tips the
    shape's +x up towards +z), then `heading` about z (turns +x towards +y).

    Its columns are where the shape's own x, y and z axes end up."""
    h, p, r = (math.radians(a) for a in (heading, pitch, roll))
    about_z = np.array(
        [[math.cos(h), -math.sin(h), 0], [math.sin(h), math.cos(h), 0], [0, 0, 1]],
    )
    about_y = np.array(
        [[math.cos(p), 0, -math.sin(p)], [0, 1, 0], [math.sin(p), 0, math.cos(p)]],
    )
    about_x = np.array(
        [[1, 0, 0], [0, math.cos(r), -math.sin(r)], [0, math.sin(r), math.cos(r)]],
    )
    return (about_z @ about_y @ about_x).astype(np.float32)


@dataclass(frozen=True)
class Ellipsoid:
    """A squashed or stretched ball: the workhorse of clay modelling (bodies, heads, eyes)."""

    centre: Vec3
    radii: Vec3
    turn: np.ndarray = field(default_factory=lambda: IDENTITY)

    def distance(self, p: np.ndarray) -> np.ndarray:
        # Into the ellipsoid's own frame: subtract the centre, undo the turn. (p @ turn is
        # turn's transpose applied to each point, and a rotation's transpose is its inverse.)
        q = (p - np.asarray(self.centre, dtype=np.float32)) @ self.turn
        r = np.asarray(self.radii, dtype=np.float32)
        # An ellipsoid has no exact distance formula. This is Inigo Quilez's estimate: exact
        # for spheres, and close to the true distance near the surface, which is the only
        # place the mesher and the blending need it to be right.
        k0 = np.linalg.norm(q / r, axis=1)
        k1 = np.linalg.norm(q / (r * r), axis=1)
        with np.errstate(divide="ignore", invalid="ignore"):
            d = k0 * (k0 - 1.0) / k1
        return np.where(k1 > 0, d, -r.min()).astype(np.float32)

    def bounds(self) -> tuple[np.ndarray, np.ndarray]:
        c, reach = np.asarray(self.centre), max(self.radii)
        return c - reach, c + reach


@dataclass(frozen=True)
class RoundCone:
    """A ball at each end, joined by a smooth taper: beaks, tails, legs, toes.

    The exact distance to a "round cone", from Inigo Quilez's catalogue of SDFs."""

    start: Vec3
    end: Vec3
    start_radius: float
    end_radius: float

    def distance(self, p: np.ndarray) -> np.ndarray:
        a = np.asarray(self.start, dtype=np.float64)
        ba = np.asarray(self.end, dtype=np.float64) - a
        r1, r2 = self.start_radius, self.end_radius
        l2 = float(ba @ ba)
        rr = r1 - r2
        a2 = l2 - rr * rr
        pa = p.astype(np.float64) - a
        y = pa @ ba
        z = y - l2
        x2 = np.sum((pa * l2 - np.outer(y, ba)) ** 2, axis=1)
        y2, z2 = y * y * l2, z * z * l2
        k = math.copysign(1.0, rr) * rr * rr * x2
        # Three regions: past the small end (its ball), behind the big end (its ball), or
        # along the side (the cone between the two balls' tangent lines).
        near_end = np.sign(z) * a2 * z2 > k
        near_start = np.sign(y) * a2 * y2 < k
        side = (np.sqrt(np.maximum(x2 * a2 / l2, 0)) + y * rr) / l2 - r1
        d = np.where(near_start, np.sqrt(x2 + y2) / l2 - r1, side)
        d = np.where(near_end, np.sqrt(x2 + z2) / l2 - r2, d)
        return d.astype(np.float32)

    def bounds(self) -> tuple[np.ndarray, np.ndarray]:
        ends = np.array([self.start, self.end])
        reach = max(self.start_radius, self.end_radius)
        return ends.min(axis=0) - reach, ends.max(axis=0) + reach


def smooth_union(a: np.ndarray, b: np.ndarray, radius: float) -> np.ndarray:
    """Join two shapes with a soft, rounded neck about `radius` wide where they meet.

    Far from the join this is the plain union (the nearer of the two surfaces). Where the
    surfaces are within `radius` of each other, it subtracts a little, which pulls the
    surface outward into the crease and fills it, like clay smoothed together with a
    thumb. A radius of 0 gives the plain, hard-edged union.

    This is the "polynomial smooth minimum": the blend is a parabola, so the neck curves
    smoothly into both shapes with no visible edge."""
    if radius <= 0:
        return np.minimum(a, b)
    h = np.maximum(radius - np.abs(a - b), 0.0) / radius
    return np.minimum(a, b) - h * h * radius * 0.25


class Lumps:
    """Smooth random bumps, to add to a distance so the surface goes gently in and out.

    This is "value noise": random numbers on a lattice of points `size` apart, smoothly
    interpolated in between, so it varies gently with no edges. Two layers (octaves) are
    added: broad lumps, plus smaller ones at half the size and a third of the height."""

    def __init__(self, seed: int, size: float, height: float) -> None:
        self._lattice = np.random.default_rng(seed).uniform(-1, 1, (32, 32, 32))
        self._lattice = self._lattice.astype(np.float32)
        self._size = size
        self._height = height

    def __call__(self, p: np.ndarray) -> np.ndarray:
        broad = self._noise(p / self._size)
        fine = self._noise(p / (self._size * 0.5) + 11.3)  # offset so the layers differ
        return (self._height * (broad + fine / 3.0)).astype(np.float32)

    def _noise(self, p: np.ndarray) -> np.ndarray:
        cell = np.floor(p)
        f = (p - cell).astype(np.float32)
        f = f * f * (3 - 2 * f)  # smoothstep, so the slope is zero at lattice points
        i = cell.astype(np.int64) % 32
        j = (i + 1) % 32
        total = np.zeros(len(p), dtype=np.float32)
        for corner in range(8):
            pick = [(corner >> axis) & 1 for axis in range(3)]
            idx = [np.where(pick[axis], j[:, axis], i[:, axis]) for axis in range(3)]
            weight = np.ones(len(p), dtype=np.float32)
            for axis in range(3):
                weight *= f[:, axis] if pick[axis] else 1 - f[:, axis]
            total += weight * self._lattice[idx[0], idx[1], idx[2]]
        return total
