"""The View: what a game shows each frame, for whichever renderer the player picked (ADR 0008).

A game never draws. Each frame it describes what's on screen as a `View`, a tuple of
`Thing`s, and the chosen renderer decides what each kind of thing looks like: flat shapes,
clay, or anything added later. So one game runs under every renderer, and one renderer
draws every game.

Like `interface.py`, this imports only the standard library (and the interface's point
types), so games and renderers can both depend on it without depending on each other.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from lorikeet.interface import Point, Polygon


@dataclass(frozen=True)
class Circle:
    radius: float
    """In projector pixels."""

    def __post_init__(self) -> None:
        if self.radius <= 0:
            raise ValueError(f"a circle's radius must be positive, got {self.radius}")


@dataclass(frozen=True)
class Outline:
    """A polygon around the thing's own origin, before it's moved or turned. Keeping the
    shape separate from where the thing is means a renderer can build it once (a mesh, a
    cached image) and afterwards only move it."""

    points: Polygon

    def __post_init__(self) -> None:
        if len(self.points) < 3:
            raise ValueError(f"an outline needs at least 3 points, got {len(self.points)}")

    def placed(self, position: Point, angle: float) -> Polygon:
        """The outline's points on the canvas: turned by `angle` radians, clockwise on
        screen (the usual rotation formula, with y growing downward), then moved to
        `position`."""
        x, y = position
        cos, sin = math.cos(angle), math.sin(angle)
        return tuple((x + px * cos - py * sin, y + px * sin + py * cos) for px, py in self.points)


@dataclass(frozen=True)
class Thing:
    """One thing on screen."""

    id: int
    """Stable from frame to frame, so a renderer can keep what it built for this thing."""

    kind: str
    """What it is, such as "terrain", "egg", "bird", "goal" or "note". Each renderer picks
    a look per kind, and a plain default for kinds it doesn't know, so a game can add a kind
    without changing this file or any renderer."""

    shape: Circle | Outline

    position: Point = (0.0, 0.0)
    """Where its origin is, in projector pixels (ADR 0005)."""

    angle: float = 0.0
    """Radians, clockwise on screen. Radians because physics (pymunk) works in them."""

    layer: int = 0
    """Back to front: lower layers are drawn first. A 3D renderer can also read it as depth."""

    pose: str = ""
    """An optional hint about what it's doing, such as "hop" or "cracked", for renderers
    that animate. Renderers that don't animate ignore it."""


@dataclass(frozen=True)
class View:
    """Everything a game shows in one frame. Within a layer, later things are drawn on top."""

    things: tuple[Thing, ...] = ()

    def __post_init__(self) -> None:
        ids = [thing.id for thing in self.things]
        repeated = sorted({i for i in ids if ids.count(i) > 1})
        if repeated:
            raise ValueError(f"thing ids must be unique in a view, repeated: {repeated}")

    def back_to_front(self) -> list[Thing]:
        """The things in the order to draw them: by layer, and within a layer in the order
        the game listed them (Python's sort keeps ties in order)."""
        return sorted(self.things, key=lambda thing: thing.layer)
