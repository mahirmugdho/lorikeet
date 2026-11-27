"""Nest's physics: the level's ground, the notes on the wall, and the egg, in pymunk.

Everything is in projector pixels with y growing downward, so gravity points down the
screen. Ground never moves: the level's terrain and the notes are static shapes, and the egg
is the only thing that moves. A note's shapes come from its piece's convex `parts`, because
the physics engine only takes convex shapes (ADR 0004).

The numbers below are tuned by feel for a 1920x1080 wall with 100 px notes.
"""

from __future__ import annotations

from collections.abc import Iterable

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


class World:
    def __init__(self, level: Level) -> None:
        self._space = pymunk.Space()
        self._space.gravity = (0.0, GRAVITY)
        for polygon in level.terrain:
            self._space.add(_ground(self._space.static_body, polygon))
        self._notes: dict[int, list[pymunk.Poly]] = {}
        self._egg: tuple[pymunk.Body, pymunk.Circle] | None = None

    def set_notes(self, pieces: Iterable[Piece]) -> None:
        """Make exactly these pieces solid. A settled piece never changes shape (ADR 0004), so
        each one is built once, when it first appears, and removed when it's gone."""
        wanted = {piece.id: piece for piece in pieces}
        for gone in self._notes.keys() - wanted.keys():
            self._space.remove(*self._notes.pop(gone))
        for piece_id in wanted.keys() - self._notes.keys():
            shapes = [_ground(self._space.static_body, part) for part in wanted[piece_id].parts]
            self._space.add(*shapes)
            self._notes[piece_id] = shapes

    def lay_egg(self, at: Point, velocity: tuple[float, float]) -> None:
        self.remove_egg()
        body = pymunk.Body(1.0, pymunk.moment_for_circle(1.0, 0.0, EGG_RADIUS))
        body.position = at
        body.velocity = velocity
        shape = pymunk.Circle(body, EGG_RADIUS)
        shape.elasticity, shape.friction = EGG_BOUNCE, EGG_GRIP
        self._space.add(body, shape)
        self._egg = (body, shape)

    def remove_egg(self) -> None:
        if self._egg is not None:
            self._space.remove(*self._egg)
            self._egg = None

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
        self._space.step(seconds)


def _ground(body: pymunk.Body, polygon: Iterable[Point]) -> pymunk.Poly:
    shape = pymunk.Poly(body, list(polygon))
    shape.elasticity, shape.friction = GROUND_BOUNCE, GROUND_GRIP
    return shape
