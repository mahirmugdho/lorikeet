"""Projector pixels to Panda3D's world and back, in one place.

The game works in projector pixels: x right, y *down*, origin top left (ADR 0005). Panda3D's
world is z-up, and its cameras look along +y. The clay camera looks straight at the wall
along +y, orthographic, with one world unit per projector pixel. So:

- projector x is world x,
- projector y is world -z (down the screen is down the world),
- world y is depth: 0 is the play layer, positive is further back, towards the backdrop.

Because the camera is orthographic, depth never moves anything on screen: a thing at
projector (x, y) lands on pixel (x, y) at any depth, and the game's 2D picture is kept
exactly.
"""

from __future__ import annotations

import math

from lorikeet.interface import Point


def to_world(point: Point, depth: float = 0.0) -> tuple[float, float, float]:
    """A projector pixel, `depth` pixels back from the play layer, in world coordinates."""
    x, y = point
    return (x, depth, -y)


def to_projector(world: tuple[float, float, float]) -> Point:
    """Where a world point lands on the projector (its depth doesn't matter)."""
    x, _, z = world
    return (x, -z)


def heading(angle: float) -> float:
    """A game angle (radians, clockwise on screen) as a Panda3D roll in degrees.

    Things in the game turn in the wall's plane, which is Panda's x-z plane: a turn about
    the camera's axis, y. Panda calls that roll, and its positive roll is clockwise seen
    from the camera, as the game's angle is, so it's the same angle in degrees."""
    return math.degrees(angle)
