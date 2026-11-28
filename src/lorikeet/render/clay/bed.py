"""The flower bed (the blossom, where the egg has to get to): how it's laid out, and how it
blooms when the egg arrives.

The bed is a mound of leaves with flowers on stems standing up out of it, half open. When
the egg gets there (the View's blossom has the pose "won"), the flowers bloom: one after
another, each opens up through its stages, grows bigger than it ends up and settles back,
and its stem grows taller. Two buds hidden in the leaves push up and open as well, so the
bed fills out. Then the whole bed sways, happily.

It's done the way stop-motion animators do it: each flower head is a separate piece of clay,
and on each frame it's swapped for the next, more open one (`kinds.flower_head`'s stages),
on twos, 12 frames a second (`motion.FPS`). Nothing here moves between those frames.

Everything here is plain numbers, so it's tested without drawing anything.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from lorikeet.render.clay.kinds import FLOWER_STAGES
from lorikeet.render.clay.motion import FPS


@dataclass(frozen=True)
class Flower:
    across: float
    """Where its stem stands, across the bed, as a share of the bed's radius."""
    stem: float
    """How tall its stem is, as a share of the bed's radius."""
    size: float
    """How big its head is when open, as a share of the bed's radius."""
    colour: int
    """Which of `PETALS` its petals are."""
    depth: float
    """How far in front of (-) or behind (+) the bed's middle it stands, in pixels."""
    bud: bool = False
    """Hidden in the leaves until the bed blooms."""


FLOWERS = (
    Flower(-0.84, 0.48, 0.7, 0, 2.0),
    Flower(-0.38, 0.86, 0.8, 1, -3.0),
    Flower(0.08, 0.6, 0.74, 2, 1.0),
    Flower(0.52, 0.92, 0.78, 3, -2.0),
    Flower(0.95, 0.42, 0.64, 1, 3.0),
    Flower(-0.62, 0.3, 0.58, 2, -6.0, bud=True),
    Flower(0.32, 0.28, 0.58, 0, -6.0, bud=True),
)
"""Five flowers of different heights, sizes and colours, and two buds among them."""

PETALS = ((240, 128, 160), (246, 150, 108), (246, 204, 84), (242, 236, 222))
"""Pink, coral, yellow and white petals."""
CENTRES = ((244, 196, 70), (244, 196, 70), (232, 132, 56), (244, 196, 70))
"""Each petal colour's centre: yellow, but orange in a yellow flower so it shows."""

STAGGER = 2
"""Frames between one flower starting to bloom and the next."""

BLOOM = ((2, 0.96), (2, 1.02), (3, 1.1), (3, 1.2), (3, 1.13), (3, 1.1))
"""A flower blooming, frame by frame: which stage of head it has, and how big it is. It
grows past where it ends up and settles back, the overshoot that makes it pop."""

BUD = ((0, 0.45), (0, 0.65), (1, 0.85), (2, 1.0), (3, 1.12), (3, 1.05), (3, 1.0))
"""A hidden bud pushing up out of the leaves and opening."""

STEM_GROWTH = 1.2
"""How much taller a stem is once its flower has bloomed."""


@dataclass(frozen=True)
class FlowerState:
    stage: int
    """Which head it has, 0 (a bud) to FLOWER_STAGES - 1 (wide open)."""
    scale: float
    """How big its head is, against its open size (0: not there at all)."""
    stem: float
    """How tall its stem is, against its normal height."""
    sway: float
    """How far its head leans, in degrees (positive: clockwise on screen)."""


def flower_state(index: int, frame: int, bloomed_at: int | None) -> FlowerState:
    """Flower `index` of `FLOWERS` on stop-motion frame `frame`, if the bed started blooming
    on frame `bloomed_at` (None: it hasn't)."""
    flower = FLOWERS[index]
    # Frames since this flower started blooming (negative: it hasn't yet).
    since = -1 if bloomed_at is None else frame - bloomed_at - STAGGER * _order(index)
    blooming = since >= 0
    sway = _sway(index, frame, happy=blooming)
    if flower.bud:
        if not blooming:
            return FlowerState(0, 0.0, 0.3, sway)  # hidden in the leaves
        stage, scale = BUD[min(since, len(BUD) - 1)]
        grown = min(1.0, 0.3 + 0.7 * since / (len(BUD) - 1))
        return FlowerState(stage, scale, grown, sway)
    if not blooming:
        return FlowerState(1, 0.9, 1.0, sway)  # half open, waiting
    stage, scale = BLOOM[min(since, len(BLOOM) - 1)]
    grown = 1 + (STEM_GROWTH - 1) * min(1.0, since / (len(BLOOM) - 1))
    return FlowerState(stage, scale, grown, sway)


def _order(index: int) -> int:
    """When each flower blooms: from the middle of the bed outwards, the buds last."""
    flower = FLOWERS[index]
    by_middle = sorted(range(len(FLOWERS)), key=lambda i: (FLOWERS[i].bud, abs(FLOWERS[i].across)))
    return by_middle.index(index) if not flower.bud else by_middle.index(index) + 1


def _sway(index: int, frame: int, happy: bool) -> float:
    """A slow nod in a breeze, each flower in its own time; quicker and wider once the bed
    has bloomed. Held for each stop-motion frame like everything else."""
    seconds = frame / FPS
    period, reach = (1.4, 6.0) if happy else (2.6, 2.5)
    return reach * math.sin(math.tau * seconds / period + index * 1.7)


assert max(stage for stage, _ in BLOOM + BUD) < FLOWER_STAGES
