"""One drop: Lori pops an egg out of the nest and it rolls. Sun springs, two-touch paper, win
and fail. pymunk only, no drawing.

The world steps a fixed 1/120 s and counts steps instead of reading a clock, so the same note
layout always plays out the same way.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum, auto
from typing import Any

import pymunk
from pymunk import Vec2d

from .level import BOARD_H, BOARD_W, PAD_TOP, Level

STEPS_PER_SECOND = 120
DT = 1 / STEPS_PER_SECOND
GRAVITY = 360.0  # px/s^2, y down
EGG_RADIUS = 6.0
NOTE_W, NOTE_H = 22.0, 4.0
ROTATE_STEP = 15  # degrees

# Spring (Sun): out speed = clamp(gain * impact, min, max), along the note's face normal.
SPRING_GAIN = 1.6
SPRING_MIN = 120.0
SPRING_MAX = 420.0
TANGENT_KEEP = 0.6  # share of along-the-note speed kept through a bounce

TOUCHES_PER_NOTE = 2
TOUCH_DEBOUNCE = 12  # steps; re-contact this soon is the same touch
LAND_SPEED = 60.0  # px/s into the ground that counts as a landing
PROGRESS_EPS = 4.0  # px closer to the blossom that counts as progress
OFF_MARGIN = 24  # px past the board edge before the egg has fallen

_EGG, _GROUND, _NOTE, _BLOSSOM = 1, 2, 3, 4


class Outcome(Enum):
    RUNNING = auto()
    WON = auto()
    FELL = auto()  # off the side of the board
    SPLAT = auto()  # hit the floor (the stone strip under the pad)
    STALLED = auto()


@dataclass(frozen=True)
class PlacedNote:
    """A note on the board: centre in board pixels, angle in degrees clockwise on screen."""

    color: str
    x: int
    y: int
    angle: int = 0

    def up_normal(self) -> Vec2d:
        a = math.radians(self.angle)
        return Vec2d(math.sin(a), -math.cos(a))


@dataclass(frozen=True)
class Event:
    kind: str  # "land", "spring" or "peel"
    step: int
    note: int = -1
    speed: float = 0.0


@dataclass
class NoteState:
    note: PlacedNote
    body: pymunk.Body
    shape: pymunk.Poly
    touches: int = 0
    last_touch: int = -(10**6)
    peeled: bool = False


class Run:
    """The egg launched from Lori's nest in `level`. Call `step()` until it stops RUNNING."""

    def __init__(self, level: Level, notes: Sequence[PlacedNote]) -> None:
        self.level = level
        self.space = pymunk.Space()
        self.space.gravity = (0.0, GRAVITY)
        self.step_count = 0
        self.outcome = Outcome.RUNNING
        self._events: list[Event] = []
        self._next_velocity: Vec2d | None = None
        self._to_peel: list[int] = []
        self._won = False

        static = self.space.static_body
        for r in level.terrain:
            corners = [(r.x, r.y), (r.x + r.w, r.y), (r.x + r.w, r.y + r.h), (r.x, r.y + r.h)]
            ground = pymunk.Poly(static, corners)
            ground.friction = 0.9
            ground.elasticity = 0.1
            ground.collision_type = _GROUND
            self.space.add(ground)

        self.notes: list[NoteState] = []
        for note in notes:
            if note.color != "sun":
                raise NotImplementedError(f"{note.color} notes come after the prototype")
            body = pymunk.Body(body_type=pymunk.Body.STATIC)
            body.position = (note.x, note.y)
            body.angle = math.radians(note.angle)
            shape = pymunk.Poly.create_box(body, (NOTE_W, NOTE_H))
            shape.friction = 0.9
            shape.collision_type = _NOTE
            self.space.add(body, shape)
            self.notes.append(NoteState(note, body, shape))
        self._note_index: dict[pymunk.Shape, int] = {ns.shape: i for i, ns in enumerate(self.notes)}

        blossom = pymunk.Circle(static, 7, offset=level.blossom)
        blossom.sensor = True
        blossom.collision_type = _BLOSSOM
        self.space.add(blossom)

        self.egg = pymunk.Body(1.0, pymunk.moment_for_circle(1.0, 0, EGG_RADIUS))
        self.egg.position = level.nest
        self.egg.velocity = level.nudge
        egg_shape = pymunk.Circle(self.egg, EGG_RADIUS)
        egg_shape.friction = 0.8
        egg_shape.elasticity = 0.1
        egg_shape.collision_type = _EGG
        self.space.add(self.egg, egg_shape)

        self.space.on_collision(_EGG, _NOTE, begin=self._note_begin, separate=self._note_separate)
        self.space.on_collision(_EGG, _GROUND, begin=self._ground_begin)
        self.space.on_collision(_EGG, _BLOSSOM, begin=self._blossom_begin)

        self._best = self._distance_to_blossom()
        self._stalled_steps = 0

    # -- stepping ---------------------------------------------------------------------------

    def step(self) -> Outcome:
        if self.outcome is not Outcome.RUNNING:
            return self.outcome
        self.space.step(DT)
        self.step_count += 1
        # Velocity and shape changes wait until the step is over; pymunk is mid-solve in callbacks.
        if self._next_velocity is not None:
            self.egg.velocity = self._next_velocity
            self._next_velocity = None
        for i in self._to_peel:
            ns = self.notes[i]
            ns.peeled = True
            self.space.remove(ns.body, ns.shape)
            self._events.append(Event("peel", self.step_count, i))
        self._to_peel.clear()
        self.outcome = self._judge()
        return self.outcome

    def run_to_end(self, max_seconds: float = 30.0) -> Outcome:
        for _ in range(int(max_seconds * STEPS_PER_SECOND)):
            if self.step() is not Outcome.RUNNING:
                break
        return self.outcome

    def drain_events(self) -> list[Event]:
        events, self._events = self._events, []
        return events

    def snapshot(self) -> tuple[object, ...]:
        """Everything that should be identical between two runs of the same layout."""
        p, v = self.egg.position, self.egg.velocity
        touches = tuple((ns.touches, ns.peeled) for ns in self.notes)
        return (self.step_count, self.outcome, p.x, p.y, v.x, v.y, self.egg.angle, touches)

    # -- rules ------------------------------------------------------------------------------

    def _judge(self) -> Outcome:
        if self._won:
            return Outcome.WON
        x, y = self.egg.position
        if y + EGG_RADIUS >= PAD_TOP and -EGG_RADIUS < x < BOARD_W + EGG_RADIUS:
            return Outcome.SPLAT
        if y > BOARD_H + OFF_MARGIN or x < -OFF_MARGIN or x > BOARD_W + OFF_MARGIN:
            return Outcome.FELL
        d = self._distance_to_blossom()
        if d < self._best - PROGRESS_EPS:
            self._best = d
            self._stalled_steps = 0
        else:
            self._stalled_steps += 1
        if self._stalled_steps >= self.level.timeout_s * STEPS_PER_SECOND:
            return Outcome.STALLED
        return Outcome.RUNNING

    def _distance_to_blossom(self) -> float:
        return self.egg.position.get_distance(self.level.blossom)

    def _face_normal(self, note: PlacedNote) -> Vec2d:
        """The note's face normal on the egg's side of the paper."""
        n = note.up_normal()
        return n if (self.egg.position - (note.x, note.y)).dot(n) >= 0 else -n

    def _note_begin(self, arbiter: pymunk.Arbiter, space: pymunk.Space, data: Any) -> None:
        i = self._note_index[arbiter.shapes[1]]
        ns = self.notes[i]
        if ns.peeled:
            arbiter.process_collision = False
            return
        if self.step_count - ns.last_touch > TOUCH_DEBOUNCE:
            ns.touches += 1
        ns.last_touch = self.step_count
        # Spring: the harder it lands, the faster it leaves, along the note's face.
        n = self._face_normal(ns.note)
        v = self.egg.velocity
        impact = max(0.0, -v.dot(n))
        out = min(SPRING_MAX, max(SPRING_MIN, SPRING_GAIN * impact))
        along = v - n * v.dot(n)
        self._next_velocity = along * TANGENT_KEEP + n * out
        self._events.append(Event("spring", self.step_count, i, impact))

    def _note_separate(self, arbiter: pymunk.Arbiter, space: pymunk.Space, data: Any) -> None:
        i = self._note_index[arbiter.shapes[1]]
        ns = self.notes[i]
        if ns.touches >= TOUCHES_PER_NOTE and not ns.peeled and i not in self._to_peel:
            self._to_peel.append(i)

    def _ground_begin(self, arbiter: pymunk.Arbiter, space: pymunk.Space, data: Any) -> None:
        speed = abs(self.egg.velocity.dot(arbiter.normal))
        if speed >= LAND_SPEED:
            self._events.append(Event("land", self.step_count, speed=speed))

    def _blossom_begin(self, arbiter: pymunk.Arbiter, space: pymunk.Space, data: Any) -> None:
        self._won = True
