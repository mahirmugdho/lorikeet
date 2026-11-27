"""Nest's rules: which notes count, the go spot, laying eggs one at a time, and how each ends.

Each frame the launcher calls `update(scene, dt)` with the newest scene (ADR 0004), then
`view()`, which describes what to show for whichever renderer is drawing (ADR 0008):

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
from lorikeet.interface import Piece, PieceState, Point, Polygon, Scene
from lorikeet.view import Circle, Outline, Thing, View

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

# Thing ids in the View, kept apart so each kind of thing has its own range: renderers rely
# on an id meaning the same thing from frame to frame.
_BLOSSOM, _GO, _NEST, _LORI = 1, 2, 3, 4
_TERRAIN, _EGGS, _NOTES = 100, 1000, 100_000

NEST_RADIUS, LORI_RADIUS = 40.0, 34.0
LORI_FROM_NEST = (-70.0, -14.0)
"""Where Lori sits: just left of her nest, facing it."""


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
        self._ground: tuple[Piece, ...] = ()  # the notes that are ground right now
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
        self._ground = tuple(piece for piece in placed if piece.id not in go_notes)
        self._world.set_notes(self._ground)
        self._lag += min(dt, MAX_CATCH_UP)
        # The tiny allowance stops float rounding from dropping a step now and then.
        while self._lag >= STEP - 1e-9:
            self._lag -= STEP
            self._step()

    def view(self) -> View:
        """What to show: the ground, the go spot, the notes, Lori and her nest, the blossom,
        and the egg in front. The notes are listed for renderers that want them (a 3D one
        can cast their shadows); a flat renderer draws nothing for them, because they're
        real paper on the wall, or the desk's sketched paper."""
        level, state = self.level, self.state
        things = [
            Thing(_TERRAIN + i, "terrain", *_centred(polygon))
            for i, polygon in enumerate(level.terrain)
        ]
        things.append(
            Thing(
                _GO, "go", Circle(level.go.radius), level.go.at, pose="on" if self._go_on else "off"
            )
        )
        for piece in self._ground:
            shape, centre = _centred(piece.outline)
            things.append(
                Thing(_NOTES + piece.id, "note", shape, centre, layer=1, pose=piece.state.value)
            )
        things.append(Thing(_NEST, "nest", Circle(NEST_RADIUS), level.nest.at, layer=1))
        won = state is State.WON
        things.append(
            Thing(
                _BLOSSOM,
                "blossom",
                Circle(level.blossom.radius),
                level.blossom.at,
                layer=1,
                pose="won" if won else "",
            )
        )
        nest_x, nest_y = level.nest.at
        lori_pose = "happy" if won else "laying" if state is State.LAYING else "idle"
        lori_at = (nest_x + LORI_FROM_NEST[0], nest_y + LORI_FROM_NEST[1])
        things.append(Thing(_LORI, "bird", Circle(LORI_RADIUS), lori_at, layer=2, pose=lori_pose))
        egg = self._world.egg
        if egg is not None:
            things.append(
                Thing(
                    _EGGS + len(self.outcomes),  # each egg is a new thing
                    "egg",
                    Circle(EGG_RADIUS),
                    egg,
                    angle=self._world.egg_angle,
                    layer=3,
                )
            )
        return View(things=tuple(things))

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


def _centred(polygon: Polygon) -> tuple[Outline, Point]:
    """`polygon` as an Outline around its own centre, and where that centre is."""
    cx = sum(x for x, _ in polygon) / len(polygon)
    cy = sum(y for _, y in polygon) / len(polygon)
    return Outline(tuple((x - cx, y - cy) for x, y in polygon)), (cx, cy)


def _on(spot: Spot, point: Point) -> bool:
    return math.dist(spot.at, point) <= spot.radius
