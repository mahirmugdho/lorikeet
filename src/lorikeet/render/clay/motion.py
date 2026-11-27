"""Stop-motion: how clay figures move, 12 frames a second, while the game runs at 60.

In a stop-motion film the animator moves the puppet a little, takes a photo, and repeats,
usually 12 times for each second of film ("shooting on twos"). Three things give it away,
and the clay renderer copies all three:

- **Poses hold.** A pose (a squat, a hop, a wing raised) changes only on those 12 frames a
  second, and holds still in between. `frame_of` turns game time into the frame number.
- **Nothing goes back exactly where it was.** Every time the puppet is touched it ends up
  a fraction of a pixel off, a hair turned, a touch bigger or smaller. `jitter` gives each
  thing a new, tiny, random offset every frame.
- **The clay creeps.** Fingers leave the surface subtly different in every photo, so its
  outline shimmers ("boil"). That's done on the GPU (see the vertex shader); this module
  only says which frame it is.

Where the *game* moves something (an egg rolling, a note being placed), that stays smooth
at the full 60 frames a second: the game's physics shouldn't stutter, and a projected egg
has to be where the physics says it is. Only the renderer's own animation steps.

Lori's poses (`bird_pose`) are written as smooth curves of time, and the animator samples
them on the 12 fps frames. When the game changes her pose, the new one takes over across a
few frames (`Animator`), as an animator would move a puppet through in-betweens.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, fields

import numpy as np

from lorikeet.render.clay.lori import FEET, NECK, RADIUS, SHOULDER
from lorikeet.render.clay.shapes import rotation

FPS = 12
"""Stop-motion frames a second."""

BLEND_FRAMES = 3
"""How many frames a new pose takes to take over from the old one."""


def frame_of(seconds: float) -> int:
    """Which stop-motion frame a moment of game time falls in."""
    return math.floor(seconds * FPS + 1e-9)


@dataclass(frozen=True)
class Jitter:
    dx: float
    """Pixels right."""
    dy: float
    """Pixels down."""
    turn: float
    """Degrees, clockwise on screen."""
    scale: float


def jitter(thing_id: int, frame: int) -> Jitter:
    """The small, random misplacement of one thing on one frame: the same all through the
    frame, different on the next. Seeded by the thing and the frame, so it's the same every
    run and two things never jitter in step."""
    rng = random.Random(thing_id * 1_000_003 + frame)
    return Jitter(
        dx=rng.uniform(-0.4, 0.4),
        dy=rng.uniform(-0.4, 0.4),
        turn=rng.uniform(-0.4, 0.4),
        scale=1 + rng.uniform(-0.005, 0.005),
    )


@dataclass(frozen=True)
class BirdPose:
    """How Lori's clay is posed. Angles in degrees, distances in pixels at radius 34."""

    squash: float = 1.0
    """Height: under 1 squashes her down (and wider), over 1 stretches her up."""
    hop: float = 0.0
    """How high off the ground she is."""
    lean: float = 0.0
    """Leaning forward, towards her nest."""
    nod: float = 0.0
    """Head up (+) or down (-)."""
    tilt: float = 0.0
    """Head tipped to one side, as birds do when they look at something."""
    wings_out: float = 0.0
    """Wings held away from her sides."""
    wings_up: float = 0.0
    """Wing tips raised."""

    def mix(self, other: BirdPose, amount: float) -> BirdPose:
        """Part way (0 to 1) from this pose to `other`."""
        return BirdPose(
            **{
                f.name: (1 - amount) * getattr(self, f.name) + amount * getattr(other, f.name)
                for f in fields(self)
            }
        )


def bird_pose(name: str, t: float) -> BirdPose:
    """Lori's pose `t` seconds into the game's pose `name` ("idle", "laying" or "happy";
    anything else is idle)."""
    if name == "laying":
        return _laying(t)
    if name == "happy":
        return _happy(t)
    return _idle(t)


def _idle(t: float) -> BirdPose:
    """Sitting by her nest: breathing, and every few seconds tipping her head to look at
    something new, as birds do."""
    breath = math.sin(2 * math.pi * t / 2.2)
    looks = (0.0, 9.0, 3.0, -6.0, 5.0)
    every = 2.6
    k = math.floor(t / every)
    # Each new look takes 0.3 s to turn to, then holds.
    turning = _ease(min((t - k * every) / 0.3, 1.0))
    tilt = looks[(k - 1) % len(looks)] * (1 - turning) + looks[k % len(looks)] * turning
    return BirdPose(squash=1 + 0.018 * breath, nod=2 * breath, tilt=tilt, wings_out=2 + 2 * breath)


def _laying(t: float) -> BirdPose:
    """Squatting down over the nest and straining a little, wings out for balance."""
    down = _ease(min(t / 0.35, 1.0))
    strain = math.sin(2 * math.pi * t * 2.5) * down
    return BirdPose(
        squash=1 - 0.1 * down + 0.025 * strain,
        lean=8 * down,
        nod=-12 * down,
        wings_out=12 * down + 4 * strain,
    )


def _happy(t: float) -> BirdPose:
    """Hopping for joy, wings flapping: crouch, spring up stretched, land squashed."""
    cycle = (t % 0.75) / 0.75
    hop, squash = 0.0, 1.0
    if cycle < 0.15:  # crouch before the jump
        squash = 1 - 0.14 * math.sin(math.pi * cycle / 0.15)
    elif cycle < 0.65:  # in the air: up and down in a parabola, stretched at the ends
        u = (cycle - 0.15) / 0.5
        hop = 18 * 4 * u * (1 - u)
        squash = 1 + 0.08 * (1 - 4 * u * (1 - u))
    elif cycle < 0.85:  # landing: squash, then spring back
        squash = 1 - 0.12 * math.sin(math.pi * (cycle - 0.65) / 0.2)
    flap = math.sin(2 * math.pi * t * 2)  # twice a second: six frames a flap at 12 fps
    return BirdPose(
        squash=squash,
        hop=hop,
        nod=10,
        tilt=6 * math.sin(2 * math.pi * t),
        wings_out=30 + 18 * flap,
        wings_up=20 + 15 * flap,
    )


def _ease(x: float) -> float:
    """Slow in and out (smoothstep), as a hand moves a puppet."""
    return x * x * (3 - 2 * x)


class Animator:
    """Keeps track of each figure's pose over time, so a pose change blends in."""

    def __init__(self) -> None:
        # thing id -> (pose name, the frame it started, the pose it started from)
        self._poses: dict[int, tuple[str, int, BirdPose]] = {}

    def pose(self, thing_id: int, name: str, now: float) -> BirdPose:
        """Lori's pose at game time `now`, held to the stop-motion frame."""
        frame = frame_of(now)
        if thing_id not in self._poses:
            self._poses[thing_id] = (name, frame, bird_pose(name, 0.0))
        current, start, previous = self._poses[thing_id]
        if name != current:
            # Start blending from wherever the old pose had got to.
            previous = self._at(current, start, previous, frame)
            self._poses[thing_id] = (name, frame, previous)
            current, start = name, frame
        return self._at(current, start, previous, frame)

    def _at(self, name: str, start: int, previous: BirdPose, frame: int) -> BirdPose:
        target = bird_pose(name, (frame - start) / FPS)
        taken_over = _ease(min((frame - start) / BLEND_FRAMES, 1.0))
        return previous.mix(target, taken_over)

    def forget(self, keep: set[int]) -> None:
        """Drop the figures that have gone."""
        for thing_id in set(self._poses) - keep:
            del self._poses[thing_id]


def bird_parts(pose: BirdPose, radius: float) -> list[np.ndarray]:
    """Where each of Lori's parts goes for `pose`: a 4x4 matrix each, in her own frame (x
    forward, z up), for the body, head, near wing and far wing (`lori.py`'s parts, in
    order). The GPU blends them per vertex by the part weights, like a puppet's armature.

    The body squashes about her feet, so they stay planted, keeping her volume about the
    same (squashed down is wider), leans about her feet and hops. The head and wings ride
    on the body and turn about the neck and shoulders."""
    s = radius / RADIUS
    feet = np.array([0.0, 0.0, FEET * s])
    wide = 1 / math.sqrt(pose.squash)
    body = (
        _moved(0, 0, pose.hop * s)
        @ _about(feet, _turn(pitch=-pose.lean))
        @ _about(feet, np.diag([wide, wide, pose.squash, 1.0]))
    )
    head = body @ _about(np.array(NECK) * s, _turn(pitch=pose.nod, roll=pose.tilt))
    shoulder = np.array(SHOULDER) * s
    near = body @ _about(shoulder * [1, -1, 1], _turn(pitch=-pose.wings_up, roll=-pose.wings_out))
    far = body @ _about(shoulder, _turn(pitch=-pose.wings_up, roll=pose.wings_out))
    return [body, head, near, far]


def _moved(x: float, y: float, z: float) -> np.ndarray:
    m = np.eye(4)
    m[:3, 3] = (x, y, z)
    return m


def _turn(pitch: float = 0.0, roll: float = 0.0) -> np.ndarray:
    """A 4x4 rotation: `roll` about x, then `pitch` about y (degrees; see shapes.rotation)."""
    m = np.eye(4)
    m[:3, :3] = rotation(pitch=pitch, roll=roll)
    return m


def _about(pivot: np.ndarray, change: np.ndarray) -> np.ndarray:
    """`change` (a 4x4) done about `pivot` instead of the origin."""
    return _moved(*pivot) @ change @ _moved(*(-pivot))
