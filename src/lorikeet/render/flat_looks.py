"""How the flat renderer draws each kind of thing: soft colours, rounded shapes, soft shadows.

A look is picked by the thing's `kind` (ADR 0008). Kinds without a look get a plain default,
so a game can add a kind before any renderer knows it.

The colours are muted on purpose. The camera finds notes by how vivid their colour is
(ADR 0006), so a vivid colour projected on the wall could look like a note to it.

Two kinds keep the light off real paper, for the same reason (anything bright or coloured
under a note shifts its colour for the camera):

- `note` draws nothing: it's real paper on the wall, or the desk's own sketched paper.
- `go` is only a ring, and its middle stays empty for the note stuck on it.

Light comes from the top left, so shadows fall down and to the right.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence

import pygame

from lorikeet.interface import Point
from lorikeet.view import Circle, Outline, Text, Thing

DEFAULT_FILL = (150, 146, 140)
DEFAULT_EDGE = (105, 101, 96)
"""The plain look for kinds without one of their own."""

TERRAIN = (163, 150, 134)
EGG, EGG_SPECKLE, EGG_SHINE = (247, 240, 226), (206, 190, 166), (255, 253, 248)
EGG_RIM = (150, 140, 124)
EGG_WHITE, YOLK = (250, 247, 238), (222, 198, 150)
"""A broken egg's puddle. The yolk is muted, well short of a yellow note's colour, so the
camera never takes it for one."""
"""Projected onto paper, a nearly white egg is just slightly brighter paper, so a darker rim
keeps its outline visible (on the desk's notes and on real ones)."""
NEST, NEST_WEAVE, NEST_EDGE = (150, 122, 92), (134, 108, 80), (112, 88, 64)
BIRD, BIRD_BELLY, BIRD_WING, BIRD_HEAD = (
    (116, 164, 142),
    (200, 216, 190),
    (92, 138, 118),
    (
        132,
        142,
        184,
    ),
)
BEAK, EYE = (226, 176, 118), (44, 40, 40)
PETAL, BLOSSOM_CENTRE = (234, 186, 200), (238, 214, 146)
GO_RING, GO_TEXT = (120, 156, 120), (96, 124, 96)
INK, SOFT_INK = (66, 62, 58), (116, 110, 104)
"""Words: dark and neutral, so projected text never looks like a note to the camera."""

ROUNDING = 10.0
"""How round terrain corners are, in pixels."""

SHADOW_OFFSET = (5, 7)
SHADOW_BLUR = 6
SHADOW_DARKNESS = 60
_MAX_SHADOWS = 256  # blurred shadows kept at once, so a long session can't grow the cache

Look = Callable[[pygame.Surface, Thing], None]


class FlatLooks:
    def __init__(self) -> None:
        pygame.font.init()
        self._font = pygame.font.Font(None, 30)  # None picks the font pygame ships with
        self._shadows: dict[tuple[object, ...], pygame.Surface] = {}
        self._fonts: dict[int, pygame.font.Font] = {}
        self._looks: dict[str, Look] = {
            "terrain": self._terrain,
            "egg": self._egg,
            "nest": self._nest,
            "bird": self._bird,
            "blossom": self._blossom,
            "go": self._go,
            "note": _nothing,
        }

    def draw(self, canvas: pygame.Surface, thing: Thing) -> None:
        if isinstance(thing.shape, Text):
            self._text(canvas, thing, thing.shape)
            return
        self._looks.get(thing.kind, _default)(canvas, thing)

    def _text(self, canvas: pygame.Surface, thing: Thing, text: Text) -> None:
        """Words centred on the thing: a "hint" in a softer ink, anything else in the dark one."""
        size = max(8, round(text.size))
        if size not in self._fonts:
            self._fonts[size] = pygame.font.Font(None, size)  # None picks pygame's own font
        color = SOFT_INK if thing.kind == "hint" else INK
        words = self._fonts[size].render(text.text, True, color)
        x, y = thing.position
        canvas.blit(words, words.get_rect(center=(round(x), round(y))))

    def _terrain(self, canvas: pygame.Surface, thing: Thing) -> None:
        if not isinstance(thing.shape, Outline):
            _default(canvas, thing)
            return
        points = thing.shape.placed(thing.position, thing.angle)
        self._polygon_shadow(canvas, points)
        _rounded_polygon(canvas, TERRAIN, points, ROUNDING)

    def _egg(self, canvas: pygame.Surface, thing: Thing) -> None:
        if thing.pose == "broken":
            _broken_egg(canvas, thing)
            return
        (x, y), r = thing.position, _radius(thing)
        self._circle_shadow(canvas, (x, y), r)
        pygame.draw.circle(canvas, EGG, (x, y), r)
        pygame.draw.circle(canvas, EGG_RIM, (x, y), r, 3)
        # A speckle that turns with the egg, so you can see it roll...
        turn = thing.angle
        speckle = (x + 0.45 * r * math.cos(turn), y + 0.45 * r * math.sin(turn))
        pygame.draw.circle(canvas, EGG_SPECKLE, speckle, 0.18 * r)
        # ...and a shine that doesn't, because the light stays put.
        pygame.draw.circle(canvas, EGG_SHINE, (x - 0.35 * r, y - 0.4 * r), 0.22 * r)

    def _nest(self, canvas: pygame.Surface, thing: Thing) -> None:
        """A bowl seen from the front and a little above: only its front wall, from the
        front edge of the rim down to the bottom, sitting on the ground at the bottom of the
        nest's circle. The hollow inside is left open, so whatever sits in the nest (Lori,
        a layer behind it) shows above the front wall, as if down inside it."""
        (x, y), r = thing.position, _radius(thing)
        centre, across = (x, y + 0.35 * r), 1.3 * r
        bottom = _lower_arc(centre, across, 0.65 * r)  # reaches the ground at y + r
        rim = _lower_arc(centre, across, 0.24 * r)
        pygame.draw.polygon(canvas, NEST, bottom + rim[::-1])
        for depth in (0.38, 0.52):  # the coils of the weave
            pygame.draw.lines(canvas, NEST_WEAVE, False, _lower_arc(centre, across, depth * r), 2)
        pygame.draw.lines(canvas, NEST_EDGE, False, rim, 3)

    def _bird(self, canvas: pygame.Surface, thing: Thing) -> None:
        """Lori: a round bird facing right, towards her nest. She hops when an egg wins and
        squats while she's laying."""
        (x, y), r = thing.position, _radius(thing)
        if thing.pose == "happy":
            y -= 12
        squat = thing.pose == "laying"
        self._circle_shadow(canvas, (x, y), r)
        body = pygame.Rect(
            0, 0, round(2 * r * (1.12 if squat else 1)), round(2 * r * (0.88 if squat else 1))
        )
        body.center = (round(x), round(y + (0.12 * r if squat else 0)))
        pygame.draw.ellipse(canvas, BIRD, body)
        _ellipse(canvas, BIRD_BELLY, (x + 0.25 * r, y + 0.35 * r), (1.1 * r, 0.9 * r))
        _ellipse(canvas, BIRD_WING, (x - 0.3 * r, y + 0.1 * r), (0.95 * r, 0.6 * r))
        _ellipse(canvas, BIRD_HEAD, (x + 0.15 * r, y - 0.55 * r), (1.3 * r, 0.75 * r))
        pygame.draw.circle(canvas, EYE, (x + 0.42 * r, y - 0.35 * r), 0.13 * r)
        pygame.draw.circle(canvas, EGG_SHINE, (x + 0.46 * r, y - 0.4 * r), 0.04 * r)
        beak = (
            (x + 0.85 * r, y - 0.22 * r),
            (x + 1.35 * r, y - 0.02 * r),
            (x + 0.85 * r, y + 0.15 * r),
        )
        pygame.draw.polygon(canvas, BEAK, beak)

    def _blossom(self, canvas: pygame.Surface, thing: Thing) -> None:
        (x, y), r = thing.position, _radius(thing) * (1.12 if thing.pose == "won" else 1.0)
        self._circle_shadow(canvas, (x, y), 0.95 * r)
        for k in range(5):
            angle = -math.pi / 2 + k * math.tau / 5
            petal = (x + 0.55 * r * math.cos(angle), y + 0.55 * r * math.sin(angle))
            pygame.draw.circle(canvas, PETAL, petal, 0.48 * r)
        pygame.draw.circle(canvas, BLOSSOM_CENTRE, (x, y), 0.38 * r)

    def _go(self, canvas: pygame.Surface, thing: Thing) -> None:
        """A ring, thicker once a note is on it, with "go" written under it."""
        (x, y), r = thing.position, _radius(thing)
        pygame.draw.circle(canvas, GO_RING, (x, y), r, 8 if thing.pose == "on" else 3)
        label = self._font.render("go", True, GO_TEXT)
        canvas.blit(label, label.get_rect(midtop=(round(x), round(y + r + 6))))

    def _polygon_shadow(self, canvas: pygame.Surface, points: Sequence[Point]) -> None:
        left = math.floor(min(x for x, _ in points))
        top = math.floor(min(y for _, y in points))
        shape = tuple((round(x - left, 1), round(y - top, 1)) for x, y in points)
        width = math.ceil(max(x for x, _ in shape))
        height = math.ceil(max(y for _, y in shape))

        def paint(layer: pygame.Surface, pad: int) -> None:
            moved = [(x + pad, y + pad) for x, y in shape]
            _rounded_polygon(layer, (0, 0, 0, SHADOW_DARKNESS), moved, ROUNDING)

        self._cast(canvas, ("polygon", shape), (width, height), paint, (left, top))

    def _circle_shadow(self, canvas: pygame.Surface, centre: Point, radius: float) -> None:
        size = math.ceil(2 * radius)

        def paint(layer: pygame.Surface, pad: int) -> None:
            pygame.draw.circle(
                layer, (0, 0, 0, SHADOW_DARKNESS), (pad + radius, pad + radius), radius
            )

        topleft = (math.floor(centre[0] - radius), math.floor(centre[1] - radius))
        self._cast(canvas, ("circle", round(radius, 1)), (size, size), paint, topleft)

    def _cast(
        self,
        canvas: pygame.Surface,
        key: tuple[object, ...],
        size: tuple[int, int],
        paint: Callable[[pygame.Surface, int], None],
        topleft: tuple[int, int],
    ) -> None:
        """Lay a soft shadow on the canvas. Blurring is slow, so each shape's shadow is
        blurred once and kept: every egg shares one, and terrain never changes."""
        pad = 3 * SHADOW_BLUR  # room for the blur to fade out
        if key not in self._shadows:
            if len(self._shadows) >= _MAX_SHADOWS:
                self._shadows.clear()
            layer = pygame.Surface((size[0] + 2 * pad + 1, size[1] + 2 * pad + 1), pygame.SRCALPHA)
            paint(layer, pad)
            self._shadows[key] = pygame.transform.gaussian_blur(
                layer, SHADOW_BLUR, repeat_edge_pixels=False
            )
        dx, dy = SHADOW_OFFSET
        canvas.blit(self._shadows[key], (topleft[0] - pad + dx, topleft[1] - pad + dy))


def _broken_egg(canvas: pygame.Surface, thing: Thing) -> None:
    """An egg that broke where it lies: its bottom half, cracked open along a zigzag, in a
    small puddle of egg, with its top half tipped over beside it."""
    (x, y), r = thing.position, _radius(thing)
    floor = y + r  # it broke lying on whatever's under it: the floor, for now
    _ellipse(canvas, EGG_WHITE, (x + 0.25 * r, floor - 0.12 * r), (2.7 * r, 0.24 * r))
    _ellipse(canvas, YOLK, (x + 0.8 * r, floor - 0.14 * r), (0.6 * r, 0.2 * r))
    bottom = [(x + px, y + py) for px, py in _half_shell(r, upper=False)]
    pygame.draw.polygon(canvas, EGG, bottom)
    pygame.draw.polygon(canvas, EGG_RIM, bottom, 3)
    # The top half, a little smaller, tipped over on its side to the right, resting on the
    # same ground as the bottom half.
    turn = math.radians(100)
    cap = [
        (
            0.8 * (px * math.cos(turn) - py * math.sin(turn)),
            0.8 * (px * math.sin(turn) + py * math.cos(turn)),
        )
        for px, py in _half_shell(r, upper=True)
    ]
    lowest = max(py for _, py in cap)
    cap = [(x + 1.25 * r + px, floor - lowest + py) for px, py in cap]
    pygame.draw.polygon(canvas, EGG, cap)
    pygame.draw.polygon(canvas, EGG_RIM, cap, 3)


def _half_shell(r: float, upper: bool) -> list[Point]:
    """Half of an egg of radius `r` round the origin, cut along a zigzag across its middle:
    the crack, from left to right, then round the curved side back to the left."""
    crack = [(-r + i * r / 3, 0.05 * r + (0.14 * r if i % 2 else -0.12 * r)) for i in range(7)]
    side = 1 if not upper else -1  # screen y grows downwards: the lower half is +y
    curve = [
        (r * math.cos(math.pi * i / 16), side * r * math.sin(math.pi * i / 16))
        for i in range(1, 16)
    ]
    return crack + curve


def _default(canvas: pygame.Surface, thing: Thing) -> None:
    if isinstance(thing.shape, Text):
        return  # words are written by FlatLooks.draw before any look is picked
    if isinstance(thing.shape, Circle):
        pygame.draw.circle(canvas, DEFAULT_FILL, thing.position, thing.shape.radius)
        pygame.draw.circle(canvas, DEFAULT_EDGE, thing.position, thing.shape.radius, 2)
    else:
        points = thing.shape.placed(thing.position, thing.angle)
        pygame.draw.polygon(canvas, DEFAULT_FILL, points)
        pygame.draw.polygon(canvas, DEFAULT_EDGE, points, 2)


def _nothing(canvas: pygame.Surface, thing: Thing) -> None:
    pass


def _radius(thing: Thing) -> float:
    return thing.shape.radius if isinstance(thing.shape, Circle) else 20.0


def _lower_arc(centre: Point, rx: float, ry: float, steps: int = 24) -> list[Point]:
    """The bottom half of an ellipse, from its right end round to its left end."""
    cx, cy = centre
    return [
        (cx + rx * math.cos(math.pi * i / steps), cy + ry * math.sin(math.pi * i / steps))
        for i in range(steps + 1)
    ]


def _ellipse(
    canvas: pygame.Surface, color: tuple[int, int, int], centre: Point, size: Point
) -> None:
    rect = pygame.Rect(0, 0, round(size[0]), round(size[1]))
    rect.center = (round(centre[0]), round(centre[1]))
    pygame.draw.ellipse(canvas, color, rect)


def _rounded_polygon(
    surface: pygame.Surface, color: Sequence[int], points: Sequence[Point], radius: float
) -> None:
    """A convex polygon with its corners rounded off, filling exactly its own outline.

    It shrinks the polygon by `radius`, then grows it back with round corners: the shrunk
    polygon, a band `radius` wide along each edge, and a circle at each corner. Too small
    to shrink that far, it's drawn with sharp corners instead.
    """
    inner = _shrunk(points, radius)
    if inner is None:
        pygame.draw.polygon(surface, color, points)
        return
    pygame.draw.polygon(surface, color, inner)
    for (ax, ay), (bx, by) in zip(inner, inner[1:] + inner[:1], strict=True):
        length = math.hypot(bx - ax, by - ay) or 1.0
        nx, ny = -(by - ay) / length * radius, (bx - ax) / length * radius
        band = ((ax + nx, ay + ny), (bx + nx, by + ny), (bx - nx, by - ny), (ax - nx, ay - ny))
        pygame.draw.polygon(surface, color, band)
    for corner in inner:
        pygame.draw.circle(surface, color, corner, radius)


def _shrunk(points: Sequence[Point], by: float) -> tuple[Point, ...] | None:
    """The convex polygon moved `by` pixels inwards along every edge, or None if it's too
    small for that (it would turn inside out)."""
    n = len(points)
    area = _twice_area(points)
    if abs(area) < 1e-9:
        return None
    inward = 1.0 if area > 0 else -1.0  # which side of each edge is inside
    lines: list[tuple[Point, Point]] = []
    for i in range(n):
        (x0, y0), (x1, y1) = points[i], points[(i + 1) % n]
        dx, dy = x1 - x0, y1 - y0
        length = math.hypot(dx, dy)
        if length < 1e-9:
            return None
        nx, ny = -dy / length * inward, dx / length * inward
        lines.append(((x0 + nx * by, y0 + ny * by), (dx, dy)))
    corners: list[Point] = []
    for i in range(n):
        (px, py), (pdx, pdy) = lines[i - 1]  # the edge coming into corner i...
        (qx, qy), (qdx, qdy) = lines[i]  # ...and the edge leaving it
        cross = pdx * qdy - pdy * qdx
        if abs(cross) < 1e-9:  # a straight corner: the two edges are one line
            corners.append((qx, qy))
            continue
        t = ((qx - px) * qdy - (qy - py) * qdx) / cross
        corners.append((px + t * pdx, py + t * pdy))
    if _twice_area(corners) * area <= 0:
        return None
    return tuple(corners)


def _twice_area(points: Sequence[Point]) -> float:
    return sum(
        x0 * y1 - x1 * y0
        for (x0, y0), (x1, y1) in zip(points, list(points[1:]) + list(points[:1]), strict=True)
    )
