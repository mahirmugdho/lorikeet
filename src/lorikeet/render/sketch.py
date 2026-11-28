"""The sketch renderer: draws a game's View in pencil on paper, with line boil.

It's the look for desk play: the game drawn by the same hand as the desk's paper notes
(`pencil`), boiling in step with them, so the whole screen looks like one sketch. It's the
flat renderer's window with pencil looks, so the window, projector and pixel handling are
shared, and it can also be picked for the wall (`--renderer sketch`).

Each thing is a light wash of colour under loose pencil lines, redrawn with fresh wobble 10
times a second. The washes are faint and keep clear of the note colours' hues, and, as in the
flat look, notes draw nothing (they're paper already) and the go ring stays empty inside.
"""

from __future__ import annotations

import math
import random
import time
from collections.abc import Callable, Sequence

import pygame

from lorikeet.interface import Point, Polygon
from lorikeet.render.flat import FlatRenderer
from lorikeet.render.pencil import (
    PENCIL,
    around,
    boil_frame,
    jittered,
    pencil_loop,
    pencil_outline,
    seeded,
)
from lorikeet.view import Circle, Outline, Text, Thing

PAPER = (240, 236, 226)
"""Warm off-white, like a sketchbook page."""

HATCH = (150, 144, 136)
"""Hatching: lighter than the outlines, so ground reads as shaded, not solid black."""

WASHES = {
    "terrain": (222, 214, 200),
    "egg": (252, 250, 244),
    "nest": (222, 204, 178),
    "bird": (206, 222, 190),  # leaf green: a hue band no note colour uses
    "blossom": (240, 222, 226),
    "blossom-centre": (240, 228, 190),
}

HATCH_SPACING = 10


class SketchLooks:
    backdrop = PAPER

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        pygame.font.init()
        self._clock = clock  # drives the boil; tests pass a fake one
        self._fonts: dict[int, pygame.font.Font] = {}
        self._looks: dict[str, Callable[[pygame.Surface, Thing, random.Random], None]] = {
            "terrain": self._terrain,
            "egg": self._egg,
            "nest": self._nest,
            "bird": self._bird,
            "blossom": self._blossom,
            "go": self._go,
            "note": self._note,
        }

    def draw(self, canvas: pygame.Surface, thing: Thing) -> None:
        rng = seeded(thing.id, boil_frame(self._clock()))
        if isinstance(thing.shape, Text):
            self._text(canvas, thing, thing.shape, rng)
            return
        self._looks.get(thing.kind, self._default)(canvas, thing, rng)

    def _terrain(self, canvas: pygame.Surface, thing: Thing, rng: random.Random) -> None:
        points = _points(thing)
        pygame.draw.polygon(canvas, WASHES["terrain"], jittered(points, rng, amount=1.5))
        _hatch(canvas, points, rng)
        pencil_outline(canvas, points, rng)

    def _egg(self, canvas: pygame.Surface, thing: Thing, rng: random.Random) -> None:
        (x, y), r = thing.position, _radius(thing)
        pygame.draw.circle(canvas, WASHES["egg"], (x, y), r)
        pencil_loop(canvas, (x, y), r, rng)
        # A speckle that turns with the egg, so you can see it roll.
        speckle = (x + 0.45 * r * math.cos(thing.angle), y + 0.45 * r * math.sin(thing.angle))
        pygame.draw.circle(canvas, PENCIL, speckle, 0.12 * r)

    def _nest(self, canvas: pygame.Surface, thing: Thing, rng: random.Random) -> None:
        """A bowl's front wall, as in the flat look: from the rim's front edge down to the
        ground, with the hollow left open so Lori shows down inside it."""
        (x, y), r = thing.position, _radius(thing)
        centre, across = (x, y + 0.35 * r), 1.3 * r
        bottom = _half_ellipse(centre, across, 0.65 * r)
        rim = _half_ellipse(centre, across, 0.24 * r)
        pygame.draw.polygon(canvas, WASHES["nest"], bottom + rim[::-1])
        _arc(canvas, centre, across, 0.65 * r, rng)
        _arc(canvas, centre, across, 0.24 * r, rng)  # the rim's front edge
        _arc(canvas, centre, 0.92 * across, 0.45 * r, rng, width=1)  # a coil of the weave

    def _bird(self, canvas: pygame.Surface, thing: Thing, rng: random.Random) -> None:
        """Lori, facing right: hops when an egg wins, squats while laying."""
        (x, y), r = thing.position, _radius(thing)
        if thing.pose == "happy":
            y -= 12
        squat = 0.12 if thing.pose == "laying" else 0.0
        rx, ry = r * (1 + squat), r * (1 - squat)
        y += squat * r
        _ellipse_wash(canvas, WASHES["bird"], (x, y), rx, ry)
        _loop(canvas, (x, y), rx, ry, rng)
        _loop(canvas, (x - 0.3 * r, y + 0.1 * r), 0.48 * r, 0.3 * r, rng)  # wing
        pygame.draw.circle(canvas, PENCIL, (x + 0.42 * r, y - 0.35 * r), 0.11 * r)  # eye
        beak = (
            (x + 0.85 * r, y - 0.22 * r),
            (x + 1.35 * r, y - 0.02 * r),
            (x + 0.85 * r, y + 0.15 * r),
        )
        pencil_outline(canvas, beak, rng)

    def _blossom(self, canvas: pygame.Surface, thing: Thing, rng: random.Random) -> None:
        (x, y), r = thing.position, _radius(thing) * (1.12 if thing.pose == "won" else 1.0)
        for k in range(5):
            angle = -math.pi / 2 + k * math.tau / 5
            petal = (x + 0.55 * r * math.cos(angle), y + 0.55 * r * math.sin(angle))
            pygame.draw.circle(canvas, WASHES["blossom"], petal, 0.46 * r)
            pencil_loop(canvas, petal, 0.46 * r, rng)
        pygame.draw.circle(canvas, WASHES["blossom-centre"], (x, y), 0.36 * r)
        pencil_loop(canvas, (x, y), 0.36 * r, rng)

    def _note(self, canvas: pygame.Surface, thing: Thing, rng: random.Random) -> None:
        """A pencil outline round the note, its paper left alone (as in the flat look)."""
        pencil_outline(canvas, around(_points(thing)), rng)

    def _go(self, canvas: pygame.Surface, thing: Thing, rng: random.Random) -> None:
        """A pencil ring, gone over twice once a note is on it. The middle stays empty: a
        real note sits there, and light on it shifts its colour for the camera."""
        (x, y), r = thing.position, _radius(thing)
        for _ in range(2 if thing.pose == "on" else 1):
            pencil_loop(canvas, (x, y), r, rng)
        label = self._font(30).render("go", True, PENCIL)
        canvas.blit(label, label.get_rect(midtop=(round(x), round(y + r + 6))))

    def _text(self, canvas: pygame.Surface, thing: Thing, text: Text, rng: random.Random) -> None:
        """Words in pencil, tilted a little differently every boil frame, as if written again."""
        words = self._font(max(8, round(text.size))).render(text.text, True, PENCIL)
        words = pygame.transform.rotate(words, rng.uniform(-1.2, 1.2))
        x, y = thing.position
        canvas.blit(words, words.get_rect(center=(round(x), round(y))))

    def _default(self, canvas: pygame.Surface, thing: Thing, rng: random.Random) -> None:
        if isinstance(thing.shape, Circle):
            pencil_loop(canvas, thing.position, thing.shape.radius, rng)
        else:
            pencil_outline(canvas, _points(thing), rng)

    def _font(self, size: int) -> pygame.font.Font:
        if size not in self._fonts:
            self._fonts[size] = pygame.font.Font(None, size)  # None picks pygame's own font
        return self._fonts[size]


class SketchRenderer(FlatRenderer):
    """The flat renderer's window, drawing in pencil on paper."""

    def __init__(self, output: str, size: tuple[int, int], display: int) -> None:
        super().__init__(output, size, display, looks=SketchLooks())


def _points(thing: Thing) -> Polygon:
    """The thing's outline on the canvas; a circle becomes a 16-sided polygon."""
    if isinstance(thing.shape, Outline):
        return thing.shape.placed(thing.position, thing.angle)
    x, y = thing.position
    r = _radius(thing)
    return tuple(
        (x + r * math.cos(k * math.tau / 16), y + r * math.sin(k * math.tau / 16))
        for k in range(16)
    )


def _radius(thing: Thing) -> float:
    return thing.shape.radius if isinstance(thing.shape, Circle) else 20.0


def _ellipse_wash(
    canvas: pygame.Surface, color: tuple[int, int, int], centre: Point, rx: float, ry: float
) -> None:
    rect = pygame.Rect(0, 0, round(2 * rx), round(2 * ry))
    rect.center = (round(centre[0]), round(centre[1]))
    pygame.draw.ellipse(canvas, color, rect)


def _loop(canvas: pygame.Surface, centre: Point, rx: float, ry: float, rng: random.Random) -> None:
    """A quick pencil ellipse: a bit lumpy, its end running past its start (like
    `pencil.pencil_loop`, but squashed)."""
    cx, cy = centre
    start = rng.uniform(0, math.tau)
    points = []
    for i in range(23):
        angle = start + i * (math.tau + 0.5) / 22
        wobble = rng.uniform(-2.0, 2.0)
        points.append((cx + (rx + wobble) * math.cos(angle), cy + (ry + wobble) * math.sin(angle)))
    pygame.draw.lines(canvas, PENCIL, False, points, 2)


def _half_ellipse(centre: Point, rx: float, ry: float, steps: int = 24) -> list[Point]:
    """The bottom half of an ellipse, from its right end round to its left end."""
    cx, cy = centre
    return [
        (cx + rx * math.cos(math.pi * i / steps), cy + ry * math.sin(math.pi * i / steps))
        for i in range(steps + 1)
    ]


def _arc(
    canvas: pygame.Surface,
    centre: Point,
    rx: float,
    ry: float,
    rng: random.Random,
    width: int = 2,
) -> None:
    """The bottom half of a quick pencil ellipse, a bit lumpy, running a little past each
    end (like `_loop`)."""
    cx, cy = centre
    points = []
    for i in range(13):
        angle = -0.1 + i * (math.pi + 0.2) / 12
        wobble = rng.uniform(-1.5, 1.5)
        points.append((cx + (rx + wobble) * math.cos(angle), cy + (ry + wobble) * math.sin(angle)))
    pygame.draw.lines(canvas, PENCIL, False, points, width)


def _hatch(canvas: pygame.Surface, polygon: Sequence[Point], rng: random.Random) -> None:
    """Diagonal pencil hatching inside the polygon. The lines are drawn on a small layer
    around it, then cut to the polygon's shape by keeping only what lies inside a mask."""
    left = math.floor(min(x for x, _ in polygon))
    top = math.floor(min(y for _, y in polygon))
    width = math.ceil(max(x for x, _ in polygon)) - left + 1
    height = math.ceil(max(y for _, y in polygon)) - top + 1
    layer = pygame.Surface((width, height), pygame.SRCALPHA)
    for start in range(-height, width, HATCH_SPACING):
        shake = rng.uniform(-1.5, 1.5)
        pygame.draw.line(
            layer, (*HATCH, 255), (start + shake, height), (start + height + shake, 0), 1
        )
    mask = pygame.Surface((width, height), pygame.SRCALPHA)
    pygame.draw.polygon(mask, (255, 255, 255, 255), [(x - left, y - top) for x, y in polygon])
    layer.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)  # outside the mask: gone
    canvas.blit(layer, (left, top))
