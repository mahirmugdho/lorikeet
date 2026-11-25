"""Glow and effect sprites in the night style: a bright ring, dithered glow dots, a hot core.

Every effect is built once from palette tones and Bayer thresholds, then blitted. There is no
alpha blending or blur anywhere: a "glow" is a pattern of solid pixels that thins outward.
"""

import random
from dataclasses import dataclass

import numpy as np
import pygame

from . import palette as pal
from .dither import BAYER4


def _surface(rgb: np.ndarray, mask: np.ndarray) -> pygame.Surface:
    h, w = mask.shape
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    for y, x in zip(*np.nonzero(mask), strict=True):
        surf.set_at((int(x), int(y)), tuple(int(v) for v in rgb[y, x]))
    return surf


def orb(radius: int, shimmer: int = 0) -> pygame.Surface:
    """A magic orb: glow dots inside a bright ring, a hot core, and a lit arc at the top left.

    `shimmer` shifts the dither pattern, so alternating values make the inside sparkle.
    """
    n = 2 * radius + 3
    c = n / 2
    y, x = np.mgrid[0:n, 0:n]
    d = np.hypot(x + 0.5 - c, y + 0.5 - c)
    rgb = np.zeros((n, n, 3), dtype=np.uint8)
    mask = np.zeros((n, n), dtype=bool)
    # Inside: dots get denser toward the centre (outer glow tone, then inner glow tone).
    t = BAYER4[(y + shimmer) % 4, (x + shimmer) % 4]
    inner = d < radius - 0.5
    density = np.clip(1.0 - d / radius, 0.0, 1.0) * 24
    dots = inner & (density > t)
    rgb[dots] = pal.MAGIC[0]
    rgb[dots & (density > t + 4)] = pal.MAGIC[1]
    mask |= dots
    ring = np.abs(d - radius) < 0.6
    rgb[ring] = pal.MAGIC[2]
    lit = ring & (x + y < n * 0.7)
    rgb[lit] = pal.MAGIC[3]
    mask |= ring
    core = d < 2.6
    rgb[core] = pal.MAGIC[3]
    rgb[d < 1.3] = pal.WHITE_HOT
    mask |= core
    return _surface(rgb, mask)


def halo(radius: int, shimmer: int = 0) -> pygame.Surface:
    """Sparse glow dots in a disc, densest near the middle. Drawn behind something that glows."""
    n = 2 * radius + 1
    c = n / 2
    y, x = np.mgrid[0:n, 0:n]
    d = np.hypot(x + 0.5 - c, y + 0.5 - c)
    t = BAYER4[(y + shimmer) % 4, (x + 2 * shimmer) % 4]
    density = np.clip(1.0 - d / radius, 0.0, 1.0) * 18
    mask = (d < radius) & (density > t + 1)
    rgb = np.zeros((n, n, 3), dtype=np.uint8)
    rgb[mask] = pal.MAGIC[0]
    rgb[mask & (density > t + 4)] = pal.MAGIC[1]
    return _surface(rgb, mask)


def ring_frames() -> list[pygame.Surface]:
    """A shock ring that pops out and thins: hot pink, then violet, then broken dots."""
    frames = []
    for i, r in enumerate((3, 5, 7, 9)):
        n = 2 * r + 3
        c = n / 2
        y, x = np.mgrid[0:n, 0:n]
        d = np.hypot(x + 0.5 - c, y + 0.5 - c)
        mask = np.abs(d - r) < 0.6
        if i >= 2:  # break the ring up as it fades
            mask &= BAYER4[y % 4, x % 4] < (12 if i == 2 else 6)
        rgb = np.zeros((n, n, 3), dtype=np.uint8)
        rgb[mask] = (pal.MAGIC[3], pal.MAGIC[2], pal.MAGIC[1], pal.MAGIC[1])[i]
        frames.append(_surface(rgb, mask))
    return frames


def smoke_frames() -> list[pygame.Surface]:
    """A puff that swells, then breaks into dots: light top-left, shade bottom-right."""
    frames = []
    for i, r in enumerate((1.6, 2.6, 3.4, 3.8, 3.8)):
        n = 9
        c = n / 2
        y, x = np.mgrid[0:n, 0:n]
        d = np.hypot(x + 0.5 - c, y + 0.5 - c)
        mask = d < r
        if i >= 3:
            mask &= BAYER4[y % 4, x % 4] < (10 if i == 3 else 4)
        rgb = np.zeros((n, n, 3), dtype=np.uint8)
        rgb[mask] = pal.SMOKE[0]
        rgb[mask & (x + y > n)] = pal.SMOKE[1]
        frames.append(_surface(rgb, mask))
    return frames


def recolor(surf: pygame.Surface, mapping: dict[pal.RGB, pal.RGB]) -> pygame.Surface:
    """Copy of `surf` with exact colours swapped (for palette variants of kit sprites)."""
    out = surf.copy()
    for y in range(out.get_height()):
        for x in range(out.get_width()):
            r, g, b, a = out.get_at((x, y))
            if a and (r, g, b) in mapping:
                out.set_at((x, y), (*mapping[(r, g, b)], a))
    return out


# -- soft light (screen resolution) ---------------------------------------------------------
# The one place the game is deliberately smooth: light laid over the pixel art. These are
# drawn with additive (glow) or multiply (vignette) blending at window resolution.


def soft_glow(radius: int, colour: pal.RGB, strength: float) -> pygame.Surface:
    """A smooth round glow for additive blending: `colour` x `strength` at the centre, 0 at the
    rim, falling off with the square of the distance so the edge melts away."""
    n = 2 * radius + 1
    y, x = np.mgrid[0:n, 0:n]
    d = np.hypot(x - radius, y - radius) / radius
    f = np.clip(1.0 - d, 0.0, 1.0) ** 2 * strength
    rgb = (np.array(colour, dtype=np.float64)[None, None, :] * f[:, :, None]).astype(np.uint8)
    return pygame.surfarray.make_surface(rgb.swapaxes(0, 1))


def vignette(width: int, height: int, strength: float) -> pygame.Surface:
    """A multiply layer: white in the middle, easing darker toward the corners."""
    y, x = np.mgrid[0:height, 0:width]
    d = np.hypot((x - width / 2) / (width / 2), (y - height / 2) / (height / 2)) / np.sqrt(2)
    f = 1.0 - strength * np.clip((d - 0.45) / 0.55, 0.0, 1.0) ** 2
    rgb = np.repeat((f * 255).astype(np.uint8)[:, :, None], 3, axis=2)
    return pygame.surfarray.make_surface(rgb.swapaxes(0, 1))


def bokeh(radius: int, colour: pal.RGB, strength: float) -> pygame.Surface:
    """An out-of-focus light for additive blending: a soft-edged disc, flat in the middle."""
    n = 2 * radius + 1
    y, x = np.mgrid[0:n, 0:n]
    d = np.hypot(x - radius, y - radius) / radius
    edge = np.clip((1.0 - d) / 0.55, 0.0, 1.0)
    f = edge * edge * (3 - 2 * edge) * strength  # smoothstep: no hard rim
    rgb = (np.array(colour, dtype=np.float64)[None, None, :] * f[:, :, None]).astype(np.uint8)
    return pygame.surfarray.make_surface(rgb.swapaxes(0, 1))


def defocus(sharp: pygame.Surface, scale: int, blur: int) -> pygame.Surface:
    """Push a board-resolution backdrop behind the scene: scale it up, blur it, then tint it
    cooler and slightly darker with a lifted floor, the way distance reads through night air.

    Expensive (tens of ms), so it runs once per scene, never per frame.
    """
    big = pygame.transform.scale_by(sharp, scale)
    soft = pygame.transform.gaussian_blur(big, blur)
    soft.fill((222, 214, 240), special_flags=pygame.BLEND_MULT)
    soft.fill((5, 3, 12), special_flags=pygame.BLEND_ADD)
    return soft


# -- the win: shield and homing sparks (after Sprite Fusion's shield and pickup grammar) ---------

S3 = float(np.sqrt(3))


def hex_shield(radius: float, t: float, gone: float, grid: float = 2.3) -> pygame.Surface:
    """A hex-cell bubble at board resolution, `t` seconds after it starts forming.

    Cells switch on from the bottom up, each with a white flash; edges are bright, insides are
    faint dither dots, and a highlight band sweeps across. At `gone` every cell flashes and
    blinks out. `radius` can shrink frame to frame, so the bubble can close in.
    """
    n = int(2 * np.ceil(radius) + 3)
    c = n / 2
    yy, xx = np.mgrid[0:n, 0:n]
    px, py = xx + 0.5 - c, yy + 0.5 - c
    u, v = px / radius, -py / radius  # v points up
    rim = np.hypot(u, v)
    inside = rim <= 1.0
    # Which hexagon each pixel falls in (axial rounding), and how near its edge it is.
    gx, gy = px / grid, py / grid
    q, r = (S3 / 3) * gx - gy / 3, (2 / 3) * gy
    s = -q - r
    rq, rr, rs = np.round(q), np.round(r), np.round(s)
    dq, dr, ds = np.abs(rq - q), np.abs(rr - r), np.abs(rs - s)
    fix_q = (dq > dr) & (dq > ds)
    rq = np.where(fix_q, -rr - rs, rq)
    rr = np.where(~fix_q & (dr > ds), -rq - rs, rr)
    hx, hy = S3 * (rq + rr / 2), 1.5 * rr
    dx, dy = np.abs(gx - hx), gy - hy
    edge = np.maximum.reduce([dx, np.abs(dx / 2 + dy * S3 / 2), np.abs(dx / 2 - dy * S3 / 2)])
    edge = edge / (S3 / 2) > 0.8
    cell = ((rq.astype(np.int64) * 73856093) ^ (rr.astype(np.int64) * 19349663)) % 997 / 997
    appear = 0.02 + (v + 1) / 2 * 0.3 + cell * 0.06
    end = gone + cell * 0.1
    alive = inside & (t >= appear) & (t <= end)
    flash = (t - appear < 0.06) | (end - t < 0.05)
    sweep = np.abs((u * 0.35 + v * 0.45 - t * 0.55) % 1.0 - 0.5) < 0.04
    bay = (BAYER4[yy % 4, xx % 4] + 0.5) / 16

    rgb = np.zeros((n, n, 3), dtype=np.uint8)
    lit_edge = alive & edge & (flash | sweep | (0.5 + rim > bay * 1.6))
    rgb[lit_edge] = pal.MAGIC[1]
    rgb[lit_edge & (rim > 0.4)] = pal.MAGIC[2]
    rgb[lit_edge & (sweep | (rim > 0.75))] = pal.MAGIC[3]
    rgb[lit_edge & flash] = pal.WHITE_HOT
    dots = alive & ~edge & (np.where(flash, 0.7, 0.08 + 0.3 * rim * rim) > bay)
    rgb[dots] = pal.MAGIC[0]
    rgb[dots & (rim > 0.7)] = pal.MAGIC[1]
    rgb[dots & flash] = pal.MAGIC[3]
    return _surface(rgb, lit_edge | dots)


@dataclass(frozen=True)
class SparkPlan:
    """Pre-run homing sparks. `paths[i][tick]` is (x, y, life_left, size, colour) or None."""

    paths: list[list[tuple[float, float, float, int, int] | None]]
    rings: list[int]  # ticks at which a small ring pops at the target
    motes: list[
        tuple[int, float, float, float, float, float, int, int]
    ]  # born, x, y, vx, vy, life, colour, size


def homing_sparks(seed: int = 5, n: int = 14, seconds: float = 1.6) -> SparkPlan:
    """Pickup-style sparks around a target at (0, 0): they burst out, slow, then curve home and
    are absorbed, each leaving a rising mote or two (and every third one a small ring).

    Run once, ahead of time, at the game's 120 ticks per second, so every win plays the same.
    """
    rng = random.Random(seed)
    dt, steps = 1 / 120, int(seconds * 120)
    live: list[list[float] | None] = []
    for i in range(n):
        a = i / n * 2 * np.pi + rng.uniform(-0.2, 0.2)
        sp = rng.uniform(75, 150)
        size = 2 if rng.random() < 0.4 else 1
        live.append(
            [0.0, 0.0, np.cos(a) * sp, np.sin(a) * sp - 20, rng.uniform(0.75, 1.05), size, i % 3]
        )
    paths: list[list[tuple[float, float, float, int, int] | None]] = [
        [None] * steps for _ in range(n)
    ]
    rings: list[int] = []
    motes: list[tuple[int, float, float, float, float, float, int, int]] = []
    absorbed = 0
    for step in range(steps):
        age = step * dt
        for i, sp_ in enumerate(live):
            if sp_ is None:
                continue
            x, y, vx, vy, life, size, colour = sp_
            if age > life:
                live[i] = None
                continue
            if age > 0.12:  # turn for home, harder the longer it has flown
                d = float(np.hypot(x, y)) or 1.0
                want, k = 190 + 450 * age, min(1.0, dt * (3 + 22 * age))
                vx += (-x / d * want - vx) * k
                vy += (-y / d * want - vy) * k
                if d < 4.5:
                    live[i] = None
                    if absorbed % 3 == 0:
                        rings.append(step)
                    absorbed += 1
                    for _ in range(2):
                        motes.append(
                            (
                                step,
                                rng.uniform(-5, 5),
                                rng.uniform(-7, 5),
                                rng.uniform(-6, 6),
                                -rng.uniform(15, 40),
                                rng.uniform(0.4, 0.8),
                                rng.randrange(2),
                                1 if rng.random() < 0.3 else 0,
                            )
                        )
                    continue
            else:  # still flying out: drag and a little gravity
                vx -= vx * 3 * dt
                vy -= vy * 3 * dt
                vy += 30 * dt
            x, y = x + vx * dt, y + vy * dt
            live[i] = [x, y, vx, vy, life, size, colour]
            paths[i][step] = (x, y, life - age, int(size), int(colour))
    return SparkPlan(paths, rings, motes)
