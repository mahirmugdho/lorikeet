"""Camera-to-projector geometry.

Games only ever see projector pixels (ADR 0005). The webcam views the projection
at an angle, so a 3x3 homography maps camera pixels onto projector pixels.
Calibration estimates it from four known points; this module computes and applies it.
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt

Points = npt.NDArray[np.float64]
"""Shape (N, 2): one (x, y) row per point."""

Homography = npt.NDArray[np.float64]
"""Shape (3, 3), normalised so the bottom-right entry is 1."""

# Above this condition number the 8x8 system is numerically singular: three or more
# corners are (nearly) collinear, so no unique homography exists.
_MAX_CONDITION = 1e12


def homography_from_corners(src: npt.ArrayLike, dst: npt.ArrayLike) -> Homography:
    """Return the homography that maps exactly four ``src`` points onto four ``dst`` points.

    Raises ``ValueError`` if either input is not 4x2, or if the corners are degenerate.
    """
    s = _as_points(src)
    d = _as_points(dst)
    if s.shape != (4, 2) or d.shape != (4, 2):
        raise ValueError(f"need exactly 4 point pairs, got {s.shape} and {d.shape}")

    # Direct linear transform with h33 fixed to 1: each pair gives two linear equations.
    a = np.zeros((8, 8))
    b = np.zeros(8)
    for i, ((x, y), (u, v)) in enumerate(zip(s, d, strict=True)):
        a[2 * i] = [x, y, 1, 0, 0, 0, -u * x, -u * y]
        a[2 * i + 1] = [0, 0, 0, x, y, 1, -v * x, -v * y]
        b[2 * i] = u
        b[2 * i + 1] = v

    if np.linalg.cond(a) > _MAX_CONDITION:
        raise ValueError("degenerate corners: three or more points are collinear")
    return np.append(np.linalg.solve(a, b), 1.0).reshape(3, 3)


def apply_homography(h: Homography, points: npt.ArrayLike) -> Points:
    """Map ``points`` through ``h``, including the perspective divide."""
    p = _as_points(points)
    homogeneous = np.column_stack([p, np.ones(len(p))]) @ h.T
    w = homogeneous[:, 2:3]
    if np.any(np.isclose(w, 0.0)):
        raise ValueError("a point maps to infinity under this homography")
    return homogeneous[:, :2] / w


def _as_points(points: npt.ArrayLike) -> Points:
    p = np.asarray(points, dtype=np.float64)
    if p.ndim != 2 or p.shape[1] != 2:
        raise ValueError(f"points must have shape (N, 2), got {p.shape}")
    return p
