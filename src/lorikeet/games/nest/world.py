"""Nest's physics: the level's ground, the notes on the wall, and the egg, in pymunk.

Everything is in projector pixels with y growing downward, so gravity points down the
screen. Ground never moves: the level's terrain and the solid notes are static shapes, and
the egg is the only thing that moves. A note's shapes come from its piece's convex `parts`,
because the physics engine only takes convex shapes (ADR 0004).

Along the bottom of the wall is the floor. An egg that touches it breaks (`egg_broken`).
The floor is the first thing that breaks eggs; anything else that should (obstacles, when
levels get them) is made the same way, with `breaking`.

Notes come in two sorts (`NoteKind`):

- **Solid** notes are ground the egg collides with: plain, or bouncy.
- **Zones** don't collide at all: the egg passes straight through (physics engines call
  shapes like this sensors). While the egg overlaps one, the zone changes its speed: a boost
  zone speeds it up the way it's going, a slow zone drags it down to a crawl, like falling
  through honey. Zones are kept out of the physics engine entirely; each step checks whether
  the egg overlaps one.

The numbers below are tuned by feel for a 1920x1080 wall with 100 px notes.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from enum import Enum

import pymunk

from lorikeet.games.nest.level import Level
from lorikeet.interface import Piece, Point

GRAVITY = 1500.0
"""Pixels per second, per second: an egg falls about 500 px in its first 0.8 s."""

EGG_RADIUS = 28.0

EGG_BOUNCE, GROUND_BOUNCE = 0.8, 0.6
"""pymunk multiplies the two, so an egg keeps about half its speed when it bounces."""

EGG_GRIP, GROUND_GRIP = 0.7, 0.9
"""Friction, multiplied the same way: high enough that an egg rolls rather than slides."""

BOUNCY_BOUNCE = 1.2
"""A bouncy note's bounce: times the egg's 0.8, the egg keeps 96% of its speed."""

BOOST_ACCELERATION = 3000.0
"""Pixels per second, per second, added along the egg's direction while it's in a boost
zone: crossing a 100 px note adds roughly 600 px/s."""
BOOST_TOP_SPEED = 1400.0

_EGG, _BREAKS = 1, 2
"""pymunk collision types: the egg, and things that break it when it touches them."""

SLOW_DRAG = 14.0
"""How hard a slow zone drags, per second. Against gravity, an egg falls through one at
about GRAVITY / SLOW_DRAG = 107 px/s, a crawl."""


class NoteKind(Enum):
    """What a note does in Nest."""

    SOLID = "solid"
    """Ground: the egg bounces off it and rolls along it."""
    BOUNCY = "bouncy"
    """Ground that throws the egg back almost as hard as it hit."""
    BOOST = "boost"
    """A zone: the egg passes through and speeds up the way it's going."""
    SLOW = "slow"
    """A zone: the egg passes through, slowed right down."""


_ZONES = frozenset({NoteKind.BOOST, NoteKind.SLOW})


class World:
    def __init__(self, level: Level) -> None:
        self._space = pymunk.Space()
        self._space.gravity = (0.0, GRAVITY)
        for polygon in level.terrain:
            self._space.add(_ground(self._space.static_body, polygon))
        width, height = level.size
        floor = pymunk.Segment(self._space.static_body, (0.0, height), (width, height), 2.0)
        floor.elasticity, floor.friction = GROUND_BOUNCE, GROUND_GRIP
        self._space.add(breaking(floor))
        self._space.on_collision(_EGG, _BREAKS, begin=self._on_break)
        self._broken = False
        self._notes: dict[int, list[pymunk.Poly]] = {}  # solid notes, in the physics engine
        self._zones: dict[int, tuple[NoteKind, list[pymunk.Poly]]] = {}  # zones, kept out
        self._egg: tuple[pymunk.Body, pymunk.Circle] | None = None

    def set_notes(self, notes: Iterable[tuple[Piece, NoteKind]]) -> None:
        """Make exactly these notes part of the world, each doing what its kind does. A
        settled piece never changes shape (ADR 0004), so each one is built once, when it
        first appears, and removed when it's gone.

        A solid note stuck on top of the egg waits: it becomes solid once the egg is clear of
        it. Made solid at once, it would overlap the egg, and the physics would shove the egg
        out hard. This is called every frame, so a waiting note is checked again each time."""
        wanted = {piece.id: (piece, kind) for piece, kind in notes}
        for gone in self._notes.keys() - wanted.keys():
            self._space.remove(*self._notes.pop(gone))
        for gone in self._zones.keys() - wanted.keys():
            del self._zones[gone]
        for piece_id in wanted.keys() - self._notes.keys() - self._zones.keys():
            piece, kind = wanted[piece_id]
            shapes = [_ground(self._space.static_body, part, kind) for part in piece.parts]
            if kind in _ZONES:
                self._zones[piece_id] = (kind, shapes)
            elif not self._overlaps_egg(shapes):
                self._space.add(*shapes)
                self._notes[piece_id] = shapes

    def _overlaps_egg(self, shapes: list[pymunk.Poly]) -> bool:
        egg = self.egg
        if egg is None:
            return False
        for shape in shapes:
            shape.cache_bb()  # a shape not yet added doesn't know where its corners are
            # Negative inside the shape, otherwise the distance to its nearest edge.
            if shape.point_query(egg).distance < EGG_RADIUS:
                return True
        return False

    def lay_egg(self, at: Point, velocity: tuple[float, float]) -> None:
        self.remove_egg()
        body = pymunk.Body(1.0, pymunk.moment_for_circle(1.0, 0.0, EGG_RADIUS))
        body.position = at
        body.velocity = velocity
        shape = pymunk.Circle(body, EGG_RADIUS)
        shape.elasticity, shape.friction = EGG_BOUNCE, EGG_GRIP
        shape.collision_type = _EGG
        self._space.add(body, shape)
        self._egg = (body, shape)
        self._broken = False

    def remove_egg(self) -> None:
        if self._egg is not None:
            self._space.remove(*self._egg)
            self._egg = None
        self._broken = False

    @property
    def egg_broken(self) -> bool:
        """Whether the egg has touched something that breaks it, such as the floor."""
        return self._broken

    def _on_break(self, arbiter: pymunk.Arbiter, space: pymunk.Space, data: object) -> None:
        self._broken = True

    @property
    def egg(self) -> Point | None:
        """Where the egg's centre is, or None if there's no egg."""
        if self._egg is None:
            return None
        x, y = self._egg[0].position
        return (x, y)

    @property
    def egg_angle(self) -> float:
        """How far the egg has rolled, in radians clockwise on screen (0 with no egg)."""
        return self._egg[0].angle if self._egg is not None else 0.0

    def step(self, seconds: float) -> None:
        if self._egg is not None:
            for kind, shapes in self._zones.values():
                if self._overlaps_egg(shapes):
                    self._zone_pushes(kind, self._egg[0], seconds)
        self._space.step(seconds)

    @staticmethod
    def _zone_pushes(kind: NoteKind, egg: pymunk.Body, seconds: float) -> None:
        velocity = egg.velocity
        speed = velocity.length
        if kind is NoteKind.BOOST and speed > 1:  # at a standstill it has no direction yet
            faster = min(speed + BOOST_ACCELERATION * seconds, max(speed, BOOST_TOP_SPEED))
            egg.velocity = velocity * (faster / speed)
        elif kind is NoteKind.SLOW:
            # A fixed fraction of its speed lost each step, so a fast egg slows hard and
            # quickly settles at a crawl, as gravity and drag balance.
            egg.velocity = velocity * math.exp(-SLOW_DRAG * seconds)


def breaking(shape: pymunk.Shape) -> pymunk.Shape:
    """Make `shape` break the egg when the egg touches it (the floor; obstacles later)."""
    shape.collision_type = _BREAKS
    return shape


def _ground(
    body: pymunk.Body, polygon: Iterable[Point], kind: NoteKind = NoteKind.SOLID
) -> pymunk.Poly:
    shape = pymunk.Poly(body, list(polygon))
    bounce = BOUNCY_BOUNCE if kind is NoteKind.BOUNCY else GROUND_BOUNCE
    shape.elasticity, shape.friction = bounce, GROUND_GRIP
    return shape
