"""How a clay egg breaks open, frame by frame.

The game says when the egg breaks (its pose turns "broken") and keeps it on the wall for a
second (`games.nest.game.BREAK_SECONDS`). The clay set fills that second the way the bloom
fills the win (`bed.py`): a short table of poses, one per stop-motion frame (12 a second).

Counting frames from the one it breaks on:

0. It hits the floor and squashes flat (the whole egg, squashed: `scene.SPLAT`).
1. Back to its shape, and the crack shows: the top half is sitting back on the bottom half,
   so the zigzag between them reads as a crack round the middle.
2. The top half lifts and tilts, hinged on the crack's right side, and the puddle starts.
3. and 4. It tips over, still hinged, sliding along the ground once it reaches it.
5. It lands on its side beside the bottom half, bouncing up a touch.
6. and on: it lies there, the puddle spread out.

Only the top half and the puddle move: the bottom half stays where the egg was. Everything
here is plain numbers, so it's tested without drawing anything.
"""

from __future__ import annotations

import math
from functools import cache

import numpy as np

from lorikeet.render.clay.kinds import EGG_CRACK
from lorikeet.render.clay.shapes import Egg, rotation

TIPS = (0.0, 0.0, -15.0, -50.0, -85.0, -106.0, -100.0)
"""How far the top half has tipped over on each frame, in degrees (negative: its dome
going over to the right)."""

SPREADS = (0.0, 0.0, 0.35, 0.6, 0.85, 1.05, 1.0)
"""How far the puddle has spread on each frame, against its full size."""

LANDED, BOUNCE = 5, 0.05
"""The frame the top half lands on its side, and how high it bounces up on that frame (as a
share of the egg's radius)."""


def top_half(radius: float, since: int) -> np.ndarray:
    """Where the broken egg's top half is `since` frames after the break: a 4x4 matrix (for
    column vectors) in the egg's own frame, which has the ground at z = -radius.

    It tips about a hinge on the crack's right side. Wherever that would push it into the
    ground it slides up along it instead, and from `LANDED` on it lies on the ground."""
    r = radius
    frame = min(max(since, 0), len(TIPS) - 1)
    height, _, depth = EGG_CRACK
    hinge = np.array([0.84 * r, 0.0, (height - depth) * r])
    turn = rotation(pitch=TIPS[frame]).astype(np.float64)
    m = np.eye(4)
    m[:3, :3] = turn
    m[:3, 3] = hinge - turn @ hinge
    lowest = float(np.min((_top_surface(r) @ turn.T)[:, 2] + m[2, 3]))
    ground = -r
    if frame >= LANDED:
        m[2, 3] += ground - lowest + (BOUNCE * r if frame == LANDED else 0.0)
    elif lowest < ground:
        m[2, 3] += ground - lowest
    return m


def puddle(since: int) -> float:
    """How far the puddle has spread `since` frames after the break (0: not yet)."""
    return SPREADS[min(max(since, 0), len(SPREADS) - 1)]


@cache
def _top_surface(radius: float) -> np.ndarray:
    """Points on the outside of the egg above the crack's lowest point: enough to find how
    low the top half reaches however it's turned. Found all at once (a few hundred rays out
    from the middle, each halved down to the surface together), so it takes milliseconds:
    it's worked out the first time an egg breaks, mid-game."""
    egg = Egg(radius)
    height, _, depth = EGG_CRACK
    up, around = np.meshgrid(
        np.linspace(0.0, 1.0, 14), np.linspace(0.0, math.tau, 36, endpoint=False)
    )
    directions = np.stack(
        [np.cos(around) * np.cos(up), np.sin(around) * np.cos(up), np.sin(up * math.pi / 2)],
        axis=-1,
    ).reshape(-1, 3)
    directions /= np.linalg.norm(directions, axis=1, keepdims=True)
    near = np.zeros(len(directions))
    far = np.full(len(directions), 2.0 * radius)
    for _ in range(30):
        mid = (near + far) / 2
        inside = egg.distance((directions * mid[:, None]).astype(np.float32)) < 0
        near, far = np.where(inside, mid, near), np.where(inside, far, mid)
    points = directions * near[:, None]
    return points[points[:, 2] > (height - depth) * radius]
