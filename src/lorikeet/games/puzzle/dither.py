"""Ordered (Bayer 4x4) dithering between palette tones. Light is never blurred or blended.

Ported from the art kit's `scene.py`, so the game's glow matches the reference background.
"""

import numpy as np
from numpy.typing import NDArray

BAYER4 = np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]])


def dither_levels(value: NDArray[np.float64], steps: int) -> NDArray[np.int_]:
    """Map a float field in [0, steps-1] to whole tone indices, breaking ties with the Bayer grid.

    `value[y, x]` between two tones lands on the lower or upper one depending on where the
    pixel sits in the 4x4 threshold pattern, so a smooth ramp becomes a crisp pixel pattern.
    """
    h, w = value.shape
    y, x = np.mgrid[0:h, 0:w]
    v = np.clip(value, 0.0, steps - 1)
    lo = np.floor(v).astype(np.int_)
    frac = v - lo
    up = frac * 16 > BAYER4[y % 4, x % 4] + 0.5
    return np.minimum(lo + up, steps - 1)


def vertical(width: int, height: int, top: float, bottom: float, steps: int) -> NDArray[np.int_]:
    """Tone indices ramping from `top` to `bottom` (fractions of the height), dithered at the seams.

    Rows above `top` get tone 0 and rows below `bottom` get the last tone.
    """
    y = np.repeat(np.arange(height, dtype=np.float64)[:, None], width, axis=1) / height
    v = np.clip((y - top) / max(bottom - top, 1e-6), 0.0, 1.0) * (steps - 1)
    return dither_levels(v, steps)


def glow(
    width: int, height: int, cx: float, cy: float, radius: float, steps: int = 4
) -> NDArray[np.int_]:
    """Tone indices for a round glow: `steps - 1` at the centre, fading to 0 at `radius`.

    The vertical distance is stretched by 1.15, as in `scene.py`, so the glow sits wide and low.
    """
    y, x = np.mgrid[0:height, 0:width]
    d = np.hypot(x - cx, (y - cy) * 1.15)
    return dither_levels(np.clip(1 - d / radius, 0.0, None) * (steps - 1), steps)
