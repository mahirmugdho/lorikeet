"""The fine surface of handled clay: fingerprints, smudges, grain and a few hairline cracks.

None of this is in the mesh, which would need millions of triangles. Instead it's a small
tiling texture, made once at startup with numpy, that tilts the surface's normal a little
at each pixel, so light catches tiny ridges and grooves that aren't really there (a "bump
map").

The texture stores *slopes*, not heights: how steeply the imagined surface rises along each
texture axis. Slope is what the lighting needs, and slopes average out correctly when the
GPU shrinks the texture for distant or small things (mipmapping): far away the ridges blur
into a plain matte surface, as they would in a photo, instead of sparkling.

Everything is built to tile, so the edges of the texture meet without a seam: the noise is
made by filtering random numbers in the frequency domain (an FFT, which treats the image as
wrapping around), and the prints and cracks measure distances the wrapped way round.

Sizes are in pixels on the projected figure, for a tile `TILE` pixels across. Lori is about
70 px tall, so a print is a fair part of her side, as a fingertip is on a small model.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

TILE = 64.0
"""How many pixels of a figure's surface one texture tile covers."""


@dataclass(frozen=True)
class Detail:
    slopes: np.ndarray
    """(n, n, 2) float32: the rise of the imagined surface per pixel along x and y."""
    cavity: np.ndarray
    """(n, n) float32, 0-1: how deep in a crack each texel is, for darkening it."""
    sheen: np.ndarray
    """(n, n) float32, around 0: a touch more sheen (+) where a fingertip left oil, less (-)
    where the clay is dry."""

    def rgba(self) -> np.ndarray:
        """Packed for the GPU, one texel per pixel: slopes in red and green, cavity in
        blue, sheen in alpha."""
        return np.dstack([self.slopes, self.cavity, self.sheen]).astype(np.float32)


def clay_detail(size: int = 1024, seed: int = 0) -> Detail:
    """A `size` x `size` tile of clay surface detail."""
    rng = np.random.default_rng(seed)
    texel = TILE / size  # pixels of surface per texel
    height = np.zeros((size, size))
    sheen = np.zeros((size, size))

    # Broad, soft thumb-pressing: gentle dips a few pixels across.
    height += 0.07 * _noise(rng, size, wavelength=6.0 / texel)
    # Smudges: streaks where clay was smeared, each patch in its own direction.
    for _ in range(4):
        angle = rng.uniform(0, np.pi)
        streaks = _noise(rng, size, wavelength=1.6 / texel, stretch=5.0, angle=angle)
        patch = _patches(rng, size, wavelength=24.0 / texel)
        height += 0.008 * streaks * patch
        sheen -= 0.15 * patch
    # Grain: the fine, matte tooth of plasticine.
    height += 0.0035 * _noise(rng, size, wavelength=0.35 / texel)
    # Fingerprints: a few partial prints, the ridges pressed in.
    for _ in range(4):
        ridges, cover = _fingerprint(rng, size, texel)
        height += 0.022 * ridges * cover
        sheen += 0.3 * cover
    # Hairline cracks, where the clay was bent.
    cavity = _cracks(rng, size, texel, count=3)
    height -= 0.03 * cavity

    # Slopes by central differences, wrapping round at the edges like the tile does.
    dx = (np.roll(height, -1, axis=1) - np.roll(height, 1, axis=1)) / (2 * texel)
    dy = (np.roll(height, -1, axis=0) - np.roll(height, 1, axis=0)) / (2 * texel)
    slopes = np.dstack([dx, dy]).astype(np.float32)
    return Detail(slopes, cavity.astype(np.float32), np.clip(sheen, -0.5, 0.5).astype(np.float32))


def _noise(
    rng: np.random.Generator,
    size: int,
    wavelength: float,
    stretch: float = 1.0,
    angle: float = 0.0,
) -> np.ndarray:
    """Smooth random bumps about `wavelength` texels apart, that tile. With `stretch` above
    1 the bumps are drawn out into streaks along `angle`.

    White noise has every frequency equally. Keeping only frequencies near 1/wavelength
    (multiplying its Fourier transform by a bump around that frequency) leaves features of
    about that size. Squeezing the bump along one direction keeps only slow variation
    that way, which stretches features into streaks."""
    spectrum = np.fft.rfft2(rng.standard_normal((size, size)))
    fy = np.fft.fftfreq(size)[:, None]
    fx = np.fft.rfftfreq(size)[None, :]
    along = fx * np.cos(angle) + fy * np.sin(angle)
    across = -fx * np.sin(angle) + fy * np.cos(angle)
    radius = np.sqrt((along * stretch) ** 2 + across**2)
    peak = 1.0 / wavelength
    keep = np.exp(-(((radius - peak) / (0.6 * peak)) ** 2))
    keep[0, 0] = 0.0  # no overall offset
    out = np.fft.irfft2(spectrum * keep, s=(size, size))
    return out / max(out.std(), 1e-12)


def _patches(rng: np.random.Generator, size: int, wavelength: float) -> np.ndarray:
    """Soft-edged patches covering about a third of the tile: 0 outside, up to 1 inside."""
    return np.clip(_noise(rng, size, wavelength) - 0.5, 0.0, 1.0)


def _wrapped_offsets(size: int, centre: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Each texel's offset from `centre`, the short way round the tiling."""
    coords = np.arange(size)
    dx = (coords[None, :] - centre[0] + size / 2) % size - size / 2
    dy = (coords[:, None] - centre[1] + size / 2) % size - size / 2
    return np.broadcast_to(dx, (size, size)), np.broadcast_to(dy, (size, size))


def _fingerprint(
    rng: np.random.Generator, size: int, texel: float
) -> tuple[np.ndarray, np.ndarray]:
    """One partial fingerprint: ridges (-1 to 1) and where the print is (0 to 1).

    The ridges are rings round the print's core, squashed into an oval and wobbled by slow
    noise so they wander like real ridges. Real prints in clay are rarely whole, so parts
    of it fade out."""
    centre = rng.uniform(0, size, 2)
    angle = rng.uniform(0, np.pi)
    half_long, half_short = rng.uniform(6.5, 8.5) / texel, rng.uniform(4.5, 5.5) / texel
    period = 0.8 / texel  # ridge spacing
    dx, dy = _wrapped_offsets(size, centre)
    u = dx * np.cos(angle) + dy * np.sin(angle)
    v = -dx * np.sin(angle) + dy * np.cos(angle)
    oval = np.sqrt((u / half_long) ** 2 + (v / half_short) ** 2)
    wobble = 0.6 * period * _noise(rng, size, wavelength=half_short)
    ridges = np.cos(2 * np.pi * (oval * half_short + wobble) / period)
    edge = np.clip((1.0 - oval) / 0.35, 0.0, 1.0)
    whole = np.clip(_noise(rng, size, wavelength=half_short * 0.8) + 0.6, 0.0, 1.0)
    return ridges, edge * edge * whole


def _cracks(rng: np.random.Generator, size: int, texel: float, count: int) -> np.ndarray:
    """A few hairline cracks, 0 to 1: short wandering lines that fade at both ends."""
    out = np.zeros((size, size))
    width = 0.07 / texel
    for _ in range(count):
        point = rng.uniform(0, size, 2)
        heading = rng.uniform(0, 2 * np.pi)
        steps = int(rng.integers(8, 14))
        for i in range(steps):
            heading += rng.normal(0, 0.45)
            nxt = point + (0.5 / texel) * np.array([np.cos(heading), np.sin(heading)])
            fade = np.sin(np.pi * (i + 0.5) / steps)  # thin at the ends, deepest midway
            _draw_line(out, point, nxt, width, fade)
            point = nxt
    return np.clip(out, 0.0, 1.0)


def _draw_line(out: np.ndarray, a: np.ndarray, b: np.ndarray, width: float, depth: float) -> None:
    """Add a soft line from `a` to `b` (in texels) to `out`, wrapping round its edges."""
    size = out.shape[0]
    reach = int(np.ceil(4 * width)) + 1
    low = np.floor(np.minimum(a, b)).astype(int) - reach
    high = np.ceil(np.maximum(a, b)).astype(int) + reach
    xs, ys = np.arange(low[0], high[0] + 1), np.arange(low[1], high[1] + 1)
    px, py = np.meshgrid(xs, ys)
    ab = b - a
    t = np.clip(((px - a[0]) * ab[0] + (py - a[1]) * ab[1]) / max(ab @ ab, 1e-12), 0.0, 1.0)
    dist = np.hypot(px - (a[0] + t * ab[0]), py - (a[1] + t * ab[1]))
    line = depth * np.exp(-((dist / width) ** 2))
    region = np.ix_(ys % size, xs % size)
    out[region] = np.maximum(out[region], line)
