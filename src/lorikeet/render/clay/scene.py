"""Keep the clay set in step with a game's View, frame by frame.

Each frame the game describes what's on screen as a `View` (ADR 0008). `ClayScene.show`
makes sure every thing in it has a clay figure on the set, puts it where the View says,
poses it, and removes figures whose things have gone. Figures are built once per kind and
size (and kept on disk, see `cache.py`), so after the first frame only transforms change.

How a thing's View maps onto the set:

- **Where.** The thing's position, at a depth from its layer: higher layers stand a little
  further forward, so Lori is in front of her nest and the egg in front of both.
- **Turn.** The thing's angle turns its figure in the wall's plane (the egg rolls).
- **Stop-motion** (see `motion.py`). Positions and turns from the game stay smooth at the
  full frame rate. On top, each figure gets its tiny per-frame jitter, and its clay boils,
  12 times a second. Ledges don't jitter (they're the physics' ground, and a set is glued
  down); their clay still creeps a little.
- **Notes** are real paper on the wall, so they get no figure, only an invisible box that
  casts their shadow onto the set (`stage.shadow_box`).
- Kinds without a clay look yet (the words, for now) aren't drawn.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from panda3d.core import NodePath

from lorikeet.render.clay.cache import built
from lorikeet.render.clay.coords import heading, to_world
from lorikeet.render.clay.figure import Figure
from lorikeet.render.clay.kinds import blossom, egg, go_ring, ledge, nest
from lorikeet.render.clay.lori import lori
from lorikeet.render.clay.motion import Animator, bird_parts, frame_of, jitter
from lorikeet.render.clay.stage import BACKDROP_DEPTH, Stage, figure_node, pose, shadow_box
from lorikeet.view import Circle, Outline, Thing, View

LAYER_DEPTH = 8.0
"""How much further forward each layer stands, in pixels."""

LORI_TURN = (-32.0, 12.0)
"""Lori's pose for the camera: turned 32 degrees to face us a little and tipped 12 towards
us, as if seen from slightly above. Her figure faces +x, the way the game has her look."""


@dataclass(frozen=True)
class Look:
    """How one kind of thing is made and handled on the clay set."""

    figure: Callable[[Thing], Figure]
    step: float
    """Mesh grid step, in pixels: finer for small, close-up figures."""
    boil: float
    """How far the clay creeps each stop-motion frame, in pixels."""
    jitter: float
    """How much of the stop-motion jitter it gets: 1 for a figure, 0 for the ground."""
    detail: float = 1.0
    """How strongly fingerprints and smudges show. Less on big flat faces, where the full
    amount reads as stucco rather than handled clay."""


def _radius(thing: Thing) -> float:
    return thing.shape.radius if isinstance(thing.shape, Circle) else 30.0


def _outline(thing: Thing) -> tuple[tuple[float, float], ...]:
    if isinstance(thing.shape, Outline):
        return tuple(thing.shape.points)
    r = _radius(thing)
    return ((-r, -r), (r, -r), (r, r), (-r, r))


LOOKS = {
    "bird": Look(lambda t: lori(_radius(t)), step=0.8, boil=0.6, jitter=1.0),
    "egg": Look(lambda t: egg(_radius(t)), step=0.8, boil=0.3, jitter=0.6),
    "nest": Look(lambda t: nest(_radius(t)), step=1.0, boil=0.35, jitter=0.4),
    "blossom": Look(lambda t: blossom(_radius(t)), step=0.8, boil=0.4, jitter=0.8),
    "go": Look(lambda t: go_ring(_radius(t)), step=1.2, boil=0.3, jitter=0.3),
    "terrain": Look(
        lambda t: ledge(_outline(t), back=BACKDROP_DEPTH + 2),
        step=1.5,
        boil=0.2,
        jitter=0.0,
        detail=0.4,
    ),
}


class ClayScene:
    def __init__(self, stage: Stage) -> None:
        self.stage = stage
        self.animator = Animator()
        self._things: dict[
            int, tuple[object, NodePath, NodePath]
        ] = {}  # id -> (key, place, figure)
        self._figures: dict[object, NodePath] = {}  # (kind, size) -> a built figure to copy

    def show(self, view: View, now: float) -> None:
        """Bring the set up to date with `view`, at game time `now` (seconds)."""
        frame = frame_of(now)
        present = set()
        for thing in view.things:
            if thing.kind == "note":
                present.add(thing.id)
                self._note(thing)
                continue
            look = LOOKS.get(thing.kind)
            if look is None:
                continue
            present.add(thing.id)
            place, figure = self._node(thing, look)
            j = jitter(thing.id, frame)
            amount = look.jitter
            x, y = thing.position
            place.setPos(
                *to_world((x + j.dx * amount, y + j.dy * amount), -LAYER_DEPTH * thing.layer)
            )
            place.setR(heading(thing.angle) + j.turn * amount)
            place.setScale(1 + (j.scale - 1) * amount)
            figure.setShaderInput("boil_amount", look.boil)
            # Each thing boils to its own pattern, so they don't creep in step.
            figure.setShaderInput("boil_seed", float(frame) + thing.id * 0.618)
            if thing.kind == "bird":
                bird = self.animator.pose(thing.id, thing.pose, now)
                pose(figure, bird_parts(bird, _radius(thing)))
        for thing_id in set(self._things) - present:
            self._things.pop(thing_id)[1].removeNode()
        self.animator.forget(present)

    def _node(self, thing: Thing, look: Look) -> tuple[NodePath, NodePath]:
        """The thing's figure on the set, made the first time it's seen. A figure has a
        `place` (where the game puts it) and inside it the figure itself."""
        key = (thing.kind, _outline(thing) if thing.kind == "terrain" else _radius(thing))
        known = self._things.get(thing.id)
        if known is not None and known[0] == key:
            return known[1], known[2]
        if known is not None:  # same thing, new size: start again
            known[1].removeNode()
        if key not in self._figures:
            mesh = built(look.figure(thing), look.step)
            self._figures[key] = figure_node(mesh, thing.kind)
        place = self.stage.root.attachNewNode(f"{thing.kind} {thing.id}")
        holder = place
        if thing.kind == "bird":
            holder = place.attachNewNode("tilt")
            holder.setP(LORI_TURN[1])
        figure = self._figures[key].copyTo(holder)
        figure.setShaderInput("detail_strength", look.detail)
        if thing.kind == "bird":
            figure.setH(LORI_TURN[0])
        self._things[thing.id] = (key, place, figure)
        return place, figure

    def _note(self, thing: Thing) -> None:
        key = ("note", _outline(thing))
        known = self._things.get(thing.id)
        if known is None or known[0] != key:
            if known is not None:
                known[1].removeNode()
            box = shadow_box(_outline(thing), BACKDROP_DEPTH)
            box.reparentTo(self.stage.root)
            self._things[thing.id] = (key, box, box)
        box = self._things[thing.id][1]
        box.setPos(*to_world(thing.position))
        box.setR(heading(thing.angle))
