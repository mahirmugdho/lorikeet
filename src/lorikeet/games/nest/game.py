"""Nest's rules: which notes count, the go spot, laying eggs one at a time, and how each ends.

Each frame the launcher calls `update(scene, dt)` with the newest scene (ADR 0004):

- **Notes.** A note is ground once it's stuck down: SETTLED, or HIDDEN (settled, and
  probably just behind a hand). A note still MOVING is in someone's hand, so the egg goes
  straight through it.
- **The go spot.** A stuck-down note whose centre is on the go spot starts the eggs. That
  note isn't ground, so it can't change the level it's starting.
- **Eggs.** One at a time: `LAY_DELAY` after the go note goes on, or after the last egg
  ends, Lori lays the next. An egg ends when it touches the blossom (the level is won, and
  no more eggs come), falls off the canvas, or stalls: it gets no closer to the blossom for
  the level's `timeout_s`. Taking the go note off stops new eggs; an egg already out
  finishes.

Time moves in fixed steps of `STEP` seconds, however long frames take. So the game runs at
the same speed on any screen, and the same notes always play out exactly the same way, which
lets the tests replay a level's solution.
"""

from __future__ import annotations

import math
from enum import Enum

from lorikeet.games.nest.level import Level, Spot
from lorikeet.games.nest.world import EGG_RADIUS, World
from lorikeet.interface import PieceState, Point, Scene

STEP = 1 / 120
"""Seconds per physics step."""

MAX_CATCH_UP = 0.25
"""The most game time one frame can add. After a long stall (a slow frame, a dragged
window) the game skips ahead instead of running hundreds of steps at once."""

LAY_DELAY = 0.75
"""Seconds before Lori lays the next egg."""

PROGRESS = 4.0
"""Pixels an egg has to get closer to the blossom to count as progress."""

_PLACED = frozenset({PieceState.SETTLED, PieceState.HIDDEN})


class State(Enum):
    WAITING = "waiting"
    """No note on the go spot."""
    LAYING = "laying"
    """The go note is on; the next egg is coming."""
    FLYING = "flying"
    """An egg is out."""
    WON = "won"
    """An egg reached the blossom."""


class Outcome(Enum):
    WON = "won"
    FELL = "fell"
    STALLED = "stalled"


class NestGame:
    def __init__(self, level: Level) -> None:
        self.level = level
        self.outcomes: list[Outcome] = []
        """How each egg so far has ended, oldest first."""
        self._world = World(level)
        self._go_on = False
        self._lag = 0.0  # game time owed, not yet stepped
        self._until_egg = LAY_DELAY
        self._closest = math.inf  # the egg's closest distance to the blossom so far
        self._since_progress = 0.0

    @property
    def state(self) -> State:
        if self.outcomes and self.outcomes[-1] is Outcome.WON:
            return State.WON
        if self._world.egg is not None:
            return State.FLYING
        return State.LAYING if self._go_on else State.WAITING

    @property
    def egg(self) -> Point | None:
        """Where the egg's centre is, or None if there's no egg out."""
        return self._world.egg

    def update(self, scene: Scene, dt: float) -> None:
        placed = [piece for piece in scene.pieces if piece.state in _PLACED]
        go_notes = {piece.id for piece in placed if _on(self.level.go, piece.center)}
        self._go_on = bool(go_notes)
        self._world.set_notes(piece for piece in placed if piece.id not in go_notes)
        self._lag += min(dt, MAX_CATCH_UP)
        # The tiny allowance stops float rounding from dropping a step now and then.
        while self._lag >= STEP - 1e-9:
            self._lag -= STEP
            self._step()

    def _step(self) -> None:
        if self.state is State.WON:
            return
        egg = self._world.egg
        if egg is None:
            self._wait_for_egg()
            return
        self._world.step(STEP)
        outcome = self._outcome()
        if outcome is not None:
            self.outcomes.append(outcome)
            self._world.remove_egg()
            self._until_egg = LAY_DELAY

    def _wait_for_egg(self) -> None:
        if not self._go_on:
            self._until_egg = LAY_DELAY  # the countdown starts again when a go note goes on
            return
        self._until_egg -= STEP
        if self._until_egg <= 0:
            self._world.lay_egg(self.level.nest.at, self.level.nest.launch)
            self._closest = math.inf
            self._since_progress = 0.0

    def _outcome(self) -> Outcome | None:
        egg = self._world.egg
        assert egg is not None
        x, y = egg
        width, height = self.level.size
        blossom = self.level.blossom
        distance = math.dist(egg, blossom.at)
        if distance <= blossom.radius + EGG_RADIUS:
            return Outcome.WON
        # Off the bottom or either side. Above the top is fine: a bounce can arc up there.
        if y - EGG_RADIUS > height or x + EGG_RADIUS < 0 or x - EGG_RADIUS > width:
            return Outcome.FELL
        if distance < self._closest - PROGRESS:
            self._closest = distance
            self._since_progress = 0.0
        else:
            self._since_progress += STEP
            if self._since_progress >= self.level.timeout_s:
                return Outcome.STALLED
        return None


def _on(spot: Spot, point: Point) -> bool:
    return math.dist(spot.at, point) <= spot.radius
