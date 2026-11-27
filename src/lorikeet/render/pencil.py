"""Drawing in a hand-drawn pencil style, with line boil and soft drop shadows.

Shared by the desk's paper notes and the sketch renderer, so both are drawn by the same hand
and boil in step. It lives with the renderers because renderers may import nothing of
Lorikeet's but the view and each other (ADR 0008); the desk is free to import it from here.

Line boil is the wobble of hand-drawn animation. Every frame was traced again by hand, so
the lines never sit exactly still. Here, each shape gets a fresh random wobble 10 times a
second (`BOIL_FPS`), seeded by the shape and the boil frame. So between boil frames it
holds still, like a drawing on paper, then the whole shape is "redrawn" at once. Hand-drawn
animation runs at 8 to 12 drawings a second; wobbling every screen refresh (60 a second)
looks like vibration, not drawing.

The wobble is only for looks. Games, and the mouse, use the exact outlines.
"""

from __future__ import annotations

import math
import random
from collections.abc import Sequence

import pygame

from lorikeet.interface import Point, Polygon

BOIL_FPS = 10
PENCIL = (62, 58, 54)
"""Soft graphite, not black."""

_MAX_SHADOWS = 256
"""Blurred shadows kept at once: about 90 KB each, so at most about 25 MB."""


def boil_frame(seconds: float) -> int:
    """Which drawing of the boil is showing at `seconds`."""
    return int(seconds * BOIL_FPS)


def seeded(shape: int, frame: int) -> random.Random:
    """The random numbers for one shape in one boil frame: the same every time, so a shape
    holds still until the next boil frame."""
    return random.Random(shape * 1_000_003 + frame)


def jittered(polygon: Polygon, rng: random.Random, amount: float, steps: int = 3) -> list[Point]:
    """`polygon`'s outline as a hand would trace it: each edge cut into `steps` pieces, and
    every point nudged by up to `amount` pixels along x and along y."""
    points: list[Point] = []
    for (ax, ay), (bx, by) in _edges(polygon):
        for i in range(steps):
            t = i / steps
            points.append(
                (
                    ax + (bx - ax) * t + rng.uniform(-amount, amount),
                    ay + (by - ay) * t + rng.uniform(-amount, amount),
                )
            )
    return points


def pencil_outline(
    canvas: pygame.Surface, polygon: Polygon, rng: random.Random, color=PENCIL
) -> None:
    """Two loose strokes along every edge, the way a quick sketch goes over a line twice."""
    for a, b in _edges(polygon):
        for _ in range(2):
            pygame.draw.lines(canvas, color, False, _stroke(a, b, rng), 2)


NOTE_GAP = 6.0
"""Pixels between a note's edge and the pencil line drawn around it."""


def around(polygon: Polygon, gap: float = NOTE_GAP) -> Polygon:
    """`polygon` grown outwards by about `gap` pixels, by moving each corner away from the
    middle. It's exact for a square note and close enough for a merged, L-shaped one."""
    cx = sum(x for x, _ in polygon) / len(polygon)
    cy = sum(y for _, y in polygon) / len(polygon)
    reach = sum(math.hypot(x - cx, y - cy) for x, y in polygon) / len(polygon) or 1.0
    grow = 1 + gap / reach
    return tuple((cx + (x - cx) * grow, cy + (y - cy) * grow) for x, y in polygon)


def pencil_loop(
    canvas: pygame.Surface, center: Point, radius: float, rng: random.Random, color=PENCIL
) -> None:
    """A quick pencil circle: a bit lumpy, and its end runs past its start."""
    cx, cy = center
    start = rng.uniform(0, math.tau)
    points = []
    for i in range(23):
        angle = start + i * (math.tau + 0.5) / 22  # 0.5 radians of overlap
        r = radius + rng.uniform(-2.5, 2.5)
        points.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
    pygame.draw.lines(canvas, color, False, points, 2)


def _stroke(a: Point, b: Point, rng: random.Random) -> list[Point]:
    """One pencil stroke from `a` to `b`: it runs a few pixels past both ends, as quick lines
    do, and bows a little in the middle."""
    (ax, ay), (bx, by) = a, b
    length = math.hypot(bx - ax, by - ay) or 1.0
    ux, uy = (bx - ax) / length, (by - ay) / length  # along the edge
    nx, ny = -uy, ux  # across it
    over_start, over_end, bow = rng.uniform(2, 7), rng.uniform(2, 7), rng.uniform(-2, 2)

    def shaky(x: float, y: float) -> Point:
        return (x + rng.uniform(-1.5, 1.5), y + rng.uniform(-1.5, 1.5))

    return [
        shaky(ax - ux * over_start, ay - uy * over_start),
        ((ax + bx) / 2 + nx * bow, (ay + by) / 2 + ny * bow),
        shaky(bx + ux * over_end, by + uy * over_end),
    ]


class Shadows:
    """Soft drop shadows. Blurring is slow, so each shape's shadow is blurred once and kept:
    notes of the same size and turn share one."""

    def __init__(self) -> None:
        self._blurred: dict[tuple[object, ...], pygame.Surface] = {}

    def draw(
        self,
        canvas: pygame.Surface,
        polygon: Sequence[Point],
        offset: Point,
        blur: int,
        alpha: int,
    ) -> None:
        """Lay `polygon`'s shadow on the canvas, moved by `offset` and blurred `blur` pixels."""
        left = math.floor(min(x for x, _ in polygon))
        top = math.floor(min(y for _, y in polygon))
        shape = tuple((round(x - left, 1), round(y - top, 1)) for x, y in polygon)
        key = (shape, blur, alpha)
        if key not in self._blurred:
            if len(self._blurred) >= _MAX_SHADOWS:
                self._blurred.clear()  # a long session can't grow it forever; it refills fast
            self._blurred[key] = _blurred_shadow(shape, blur, alpha)
        pad = 3 * blur  # room for the blur to fade out
        canvas.blit(self._blurred[key], (left - pad + offset[0], top - pad + offset[1]))


def _blurred_shadow(shape: Sequence[Point], blur: int, alpha: int) -> pygame.Surface:
    pad = 3 * blur
    width = math.ceil(max(x for x, _ in shape)) + 2 * pad + 1
    height = math.ceil(max(y for _, y in shape)) + 2 * pad + 1
    layer = pygame.Surface((width, height), pygame.SRCALPHA)
    pygame.draw.polygon(layer, (0, 0, 0, alpha), [(x + pad, y + pad) for x, y in shape])
    # Edges fade into transparency rather than copying the border outwards.
    return pygame.transform.gaussian_blur(layer, blur, repeat_edge_pixels=False)


def _edges(polygon: Sequence[Point]) -> list[tuple[Point, Point]]:
    points = list(polygon)
    return list(zip(points, points[1:] + points[:1], strict=True))
