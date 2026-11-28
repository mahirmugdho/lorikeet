"""Keep the clay set in step with a game's View, frame by frame.

Each frame the game describes what's on screen as a `View` (ADR 0008). `ClayScene.show`
makes sure every thing in it has a clay figure on the set, puts it where the View says,
poses it, and removes figures whose things have gone. Figures are built once per kind and
size (and kept on disk, see `cache.py`), so after the first frame only transforms change.

How a thing's View maps onto the set:

- **Where.** The thing's position, at a depth from its layer: higher layers stand a little
  further forward, so Lori is in front of her nest and the egg in front of both.
- **Turn.** The thing's angle turns its figure in the wall's plane. The egg tumbles as it
  rolls; it's egg-shaped but the game rolls a ball, so it's lifted or lowered a little to
  keep its lowest point where the ball's is, and it rocks along the ground like an egg.
  When it breaks (pose "broken"), it squashes flat for one stop-motion frame, then it's
  swapped for its broken pieces, which play out the break (`breaking.py`): the crack
  shows, the top half tips over beside the bottom one, and the puddle spreads.
- **Stop-motion** (see `motion.py`). Positions and turns from the game stay smooth at the
  full frame rate. On top, each figure gets its tiny per-frame jitter, and its clay boils,
  12 times a second. Ledges don't jitter (they're the physics' ground, and a set is glued
  down); their clay still creeps a little.
- **Notes** are real paper on the wall, so they get no figure: an invisible box that casts
  their shadow onto the set (`stage.shadow_box`), and a rope of dark clay just outside the
  paper (`rope.py`), so players see the note counts.
- **The go disc** is pressed onto the backdrop where the go note goes, and gives a little
  as the note goes on.
- **The blossom** is a bed of flowers that blooms when the egg gets there (`bed.py`).
- **Words** (the View's Text things) are written in clay letters stuck onto the backdrop
  (`clayfont.py`): each letter is built once and copied, and each jitters on its own.
"""

from __future__ import annotations

from collections.abc import Callable, Hashable
from dataclasses import dataclass

import numpy as np
from panda3d.core import LMatrix4f, NodePath, PTA_LVecBase3f, TransformState

from lorikeet.render.clay.bed import CENTRES, FLOWERS, PETALS, flower_state
from lorikeet.render.clay.breaking import puddle, top_half
from lorikeet.render.clay.builder import BuildNow, Builds
from lorikeet.render.clay.clayfont import LETTERS, ROPE, X_HEIGHT, glyph, layout
from lorikeet.render.clay.colour import linear
from lorikeet.render.clay.coords import heading, to_world
from lorikeet.render.clay.figure import MAX_CLAYS, ClayMesh, Figure, Packed
from lorikeet.render.clay.kinds import (
    FLOWER_STAGES,
    GO_THICKNESS,
    bed_leaves,
    egg,
    egg_bottom,
    egg_puddle,
    egg_top,
    flower_head,
    go_disc,
    ledge,
    nest,
    stem,
)
from lorikeet.render.clay.lori import lori
from lorikeet.render.clay.motion import Animator, bird_parts, frame_of, jitter
from lorikeet.render.clay.rope import rope
from lorikeet.render.clay.stage import BACKDROP_DEPTH, Stage, figure_node, pose, shadow_box
from lorikeet.view import Circle, Outline, Text, Thing, View

LAYER_DEPTH = 6.0
"""How much further forward each layer stands, in pixels. Small, so everything stays close
to the ledges it rests on: Lori sits in her nest one layer behind its middle (inside the
bowl, see `kinds.nest`), and the egg comes out one layer in front of it."""

LORI_TURN = (-32.0, 12.0)
"""Lori's pose for the camera: turned 32 degrees to face us a little and tipped 12 towards
us, as if seen from slightly above. Her figure faces +x, the way the game has her look."""

NOTE_BOIL, NOTE_JITTER = 0.3, 0.5
"""How much a note's rope creeps and jitters each stop-motion frame: a little, so it's alive
like the figures but never strays onto the paper."""

SPLAT = (1.18, 0.78)
"""The egg's width and height on the frame it hits the floor, before it breaks open."""

GO_PRESS = (0.94, 1.04)
"""The go disc's size on the frames after the go note goes on: it gives, then springs back."""

HEAD_SIZE, STEM_LENGTH = 0.9, 1.0
"""What the bed's flower heads and stems are built at, as a share of the bed's radius; each
flower is scaled from there (`bed.FLOWERS`)."""

LETTER_STEP = 0.75
"""The mesh step for clay letters, in pixels at their built size: fine enough for round
ropes, coarse enough that a screenful of words stays light on the graphics card."""
SOFT_LETTERS = (128, 118, 106)
"""Hints are written in a lighter clay than messages, as the flat looks use a softer ink."""
TEXT_XHEIGHT = 0.45
"""A Text's x-height, as a share of its `size` (as for a printed font)."""
SMALL_PER_FRAME = 6
"""How many small figures (letters) can join the set in a frame, for each big one."""
LETTER_JITTER = 0.5
"""How far each letter jitters each stop-motion frame, in pixels."""

TIPPED = {"bird": LORI_TURN[1], "nest": LORI_TURN[1]}
"""Figures tipped towards the camera, as if seen from slightly above, in degrees. The nest
tips with Lori, so she sits in it, and its rim shows a sliver of the far side."""


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
    depth: float | None = None
    """Where it stands, in pixels behind the play layer, instead of where its layer puts it:
    for things pressed onto the backdrop."""


def _radius(thing: Thing) -> float:
    return thing.shape.radius if isinstance(thing.shape, Circle) else 30.0


def _outline(thing: Thing) -> tuple[tuple[float, float], ...]:
    if isinstance(thing.shape, Outline):
        return tuple(thing.shape.points)
    r = _radius(thing)
    return ((-r, -r), (r, -r), (r, r), (-r, r))


BROKEN_EGG = Look(lambda t: egg_bottom(_radius(t)), step=0.6, boil=0.3, jitter=0.4)
"""The egg once it's broken: its bottom half is its figure, and its top half and puddle
are added round it (`ClayScene._breaking`)."""

BROKEN_PIECES = {
    "top": (egg_top, 0.6),
    "puddle": (egg_puddle, 0.6),
}
"""The rest of a broken egg: each piece's recipe and grid step."""

LOOKS = {
    "bird": Look(lambda t: lori(_radius(t)), step=1.0, boil=0.6, jitter=1.0),
    "egg": Look(lambda t: egg(_radius(t)), step=0.8, boil=0.3, jitter=0.6),
    "nest": Look(lambda t: nest(_radius(t)), step=1.0, boil=0.35, jitter=0.4),
    # The blossom's own figure is the bed's leaves; its flowers are added round it (_bed).
    "blossom": Look(lambda t: bed_leaves(_radius(t)), step=1.0, boil=0.35, jitter=0.5),
    "go": Look(
        lambda t: go_disc(_radius(t)),
        step=1.2,
        boil=0.3,
        jitter=0.4,
        depth=BACKDROP_DEPTH - GO_THICKNESS / 2 - 1,  # its back just touching the backdrop
    ),
    "terrain": Look(
        lambda t: ledge(_outline(t), back=BACKDROP_DEPTH + 2),
        step=2.0,  # big and flat, and mostly hidden (only the front shows): a coarser grid
        boil=0.2,
        jitter=0.0,
        detail=0.4,
    ),
}


class ClayScene:
    def __init__(
        self,
        stage: Stage,
        builder: Builds | None = None,
        new_per_frame: int = 0,
        prefetch_font: bool = False,
    ) -> None:
        """`builder` makes the figures: built on the spot unless given (see `builder.py`).
        `new_per_frame` limits how many newly built figures join the set in one frame (0: no
        limit). Each has to be loaded onto the graphics card, which for a big one (Lori, a
        ledge) takes some milliseconds, so in a live window they're let in one a frame,
        rather than several landing in the same frame and making it late. With
        `prefetch_font`, every letter is built from the start, not just those the words on
        screen need (for a live window, so later words are ready in time)."""
        self.stage = stage
        self.things = stage.root.attachNewNode("things")
        """Every thing's figure goes under here, so they can be hidden together (`hold`)."""
        self.missing = 0
        """How many things in the last View weren't on the set, still being built."""
        self._asked: set[Hashable] = set()  # every figure the View's things have needed
        self.builder: Builds = builder if builder is not None else BuildNow()
        self._new_per_frame = new_per_frame
        self._new = 0  # newly built figures let in this frame
        self._new_small = 0  # and small ones (letters)
        self.animator = Animator()
        self._things: dict[
            int, tuple[object, NodePath, NodePath]
        ] = {}  # id -> (key, place, figure)
        self._figures: dict[object, NodePath] = {}  # (kind, size) -> a built figure to copy
        self._lowest: dict[object, np.ndarray] = {}  # egg figure -> its lowest point per degree
        self._beds: dict[int, list[tuple[NodePath, NodePath, NodePath, list[NodePath]]]] = {}
        self._bloomed: dict[int, int] = {}  # bed id -> the frame it started blooming
        self._pressed: dict[int, tuple[str, int]] = {}  # go id -> (pose, frame it began)
        self._broke_at: dict[int, int] = {}  # egg id -> the frame it broke
        self._breaks: dict[int, tuple[NodePath, NodePath]] = {}  # egg id -> top half, puddle
        self._font_ready = not prefetch_font  # whether every letter wanted is built

    def show(self, view: View, now: float) -> None:
        """Bring the set up to date with `view`, at game time `now` (seconds)."""
        frame = frame_of(now)
        present = set()
        self._new = self._new_small = 0
        self.missing = 0
        self._prefetch_font()
        for thing in view.things:
            if isinstance(thing.shape, Text):
                present.add(thing.id)
                self._words(thing, thing.shape, frame)
                continue
            if thing.kind == "note":
                present.add(thing.id)
                self._note(thing, frame)
                continue
            look = LOOKS.get(thing.kind)
            if look is None:
                continue
            present.add(thing.id)
            splat = broken = False
            since = 0  # stop-motion frames since it broke
            if thing.kind == "egg" and thing.pose == "broken":
                since = frame - self._broke_at.setdefault(thing.id, frame)
                splat, broken = since == 0, since > 0
                if broken:
                    look = BROKEN_EGG
            node = self._node(thing, look, "broken" if broken else "")
            if node is None:
                self.missing += 1
                continue  # its figure is still being built: it joins the set when ready
            place, figure = node
            j = jitter(thing.id, frame)
            amount = look.jitter
            x, y = thing.position
            depth = -LAYER_DEPTH * thing.layer if look.depth is None else look.depth
            place.setPos(*to_world((x + j.dx * amount, y + j.dy * amount), depth))
            place.setR(heading(thing.angle) + j.turn * amount)
            place.setScale(1 + (j.scale - 1) * amount)
            figure.setShaderInput("boil_amount", look.boil)
            # Each thing boils to its own pattern, so they don't creep in step.
            figure.setShaderInput("boil_seed", float(frame) + thing.id * 0.618)
            if thing.kind == "bird":
                bird = self.animator.pose(thing.id, thing.pose, now)
                pose(figure, bird_parts(bird, _radius(thing)))
            elif thing.kind == "egg" and broken:
                place.setR(j.turn * amount)  # the pieces lie upright, however it rolled
                self._breaking(thing, place, frame, since)
            elif thing.kind == "egg":
                # Have its broken pieces built ahead of time, so they're ready the moment it
                # breaks (it's only shown broken for a second).
                self._broken_pieces(thing)
                lowest = self._lowest[self._things[thing.id][0]]
                roll = round(place.getR()) % 360
                place.setZ(place.getZ() - _radius(thing) - lowest[roll])
                if splat:  # flattened against the floor, its bottom staying put
                    wide, tall = SPLAT
                    sx, sy, sz = place.getScale()
                    place.setScale(sx * wide, sy, sz * tall)
                    place.setZ(place.getZ() - (1 - tall) * _radius(thing))
            elif thing.kind == "go":
                place.setScale(place.getScale() * self._press(thing, frame))
            elif thing.kind == "blossom":
                self._bed(thing, place, frame)
        for thing_id in set(self._things) - present:
            self._things.pop(thing_id)[1].removeNode()
            for state in (self._beds, self._bloomed, self._pressed, self._broke_at, self._breaks):
                state.pop(thing_id, None)
        self.animator.forget(present)

    def _node(
        self, thing: Thing, look: Look, variant: str = ""
    ) -> tuple[NodePath, NodePath] | None:
        """The thing's figure on the set, made the first time it's seen, or None while its
        figure is being built. A figure has a `place` (where the game puts it) and inside it
        the figure itself. A `variant` (a broken egg) is a different figure for the same
        thing, swapped in for the old one."""
        size = _outline(thing) if thing.kind == "terrain" else _radius(thing)
        key = (thing.kind, size, variant)
        known = self._things.get(thing.id)
        if known is not None and known[0] == key:
            return known[1], known[2]
        if known is not None:  # same thing, new size: start again
            self._things.pop(thing.id)[1].removeNode()
        built = self._figure(key, lambda: look.figure(thing), look.step, thing.kind)
        if built is None:
            return None
        place = self.things.attachNewNode(f"{thing.kind} {thing.id}")
        holder = place
        if thing.kind in TIPPED:
            holder = place.attachNewNode("tilt")
            holder.setP(TIPPED[thing.kind])
        figure = built.copyTo(holder)
        figure.setShaderInput("detail_strength", look.detail)
        if thing.kind == "bird":
            figure.setH(LORI_TURN[0])
        self._things[thing.id] = (key, place, figure)
        return place, figure

    def hold(self, holding: bool) -> None:
        """Hide every thing on the set (the backdrop stays), or show them again: so the set
        can be filled in out of sight while it loads, then shown all at once."""
        if holding:
            self.things.hide()
        else:
            self.things.show()

    def _figure(
        self,
        key: Hashable,
        recipe: Callable[[], Figure],
        step: float,
        name: str,
        small: bool = False,
        counted: bool = True,
    ) -> NodePath | None:
        """A built figure to copy onto the set, or None while it's being built. A `small`
        one (a letter) is quick to load onto the graphics card, so it doesn't wait its turn
        behind the big figures (`new_per_frame`): a few of them come each frame alongside.
        `counted` figures are needed by what's on the View now (not built ahead), and count
        towards `progress`."""
        if counted:
            self._asked.add(key)
        if key in self._figures:
            return self._figures[key]
        if self._new_per_frame:
            if small and self._new_small >= SMALL_PER_FRAME * self._new_per_frame:
                return None
            if not small and self._new >= self._new_per_frame:
                return None  # enough new figures this frame: this one can come next frame
        mesh = self.builder.mesh(key, recipe, step)
        if mesh is None:
            return None
        self._figures[key] = figure_node(mesh, name)
        if name == "egg":
            self._lowest[key] = _lowest_per_degree(mesh)
        if small:
            self._new_small += 1
        else:
            self._new += 1
        return self._figures[key]

    def _letter(self, char: str, counted: bool = True) -> NodePath | None:
        return self._figure(
            ("letter", char), lambda: glyph(char), LETTER_STEP, "letter", True, counted
        )

    def progress(self) -> float:
        """How much of what the View's things have needed so far is built, 0 to 1: every
        figure and letter counts the same."""
        if not self._asked:
            return 1.0
        return sum(key in self._figures for key in self._asked) / len(self._asked)

    def _prefetch_font(self) -> None:
        """Have every letter built, from the first frame: words the game shows later (the
        win message) are then ready when they're needed."""
        if not self._font_ready:
            self._font_ready = all(
                [self._letter(char, counted=False) is not None for char in LETTERS]
            )

    def _words(self, thing: Thing, text: Text, frame: int) -> None:
        """A Text thing in clay letters, stuck onto the backdrop, centred on its position.
        Hidden until all its letters are built, so it never shows half written."""
        key = ("words", text.text, round(text.size), thing.kind)
        known = self._things.get(thing.id)
        if known is None or known[0] != key:
            letters = {char: self._letter(char) for char, _ in layout(text.text)[0]}
            if any(built is None for built in letters.values()):
                self.missing += 1
                return  # any old words stay up until the new ones' letters are built
            if known is not None:
                known[1].removeNode()
            place = self.things.attachNewNode(f"{thing.kind} {thing.id}")
            scale = TEXT_XHEIGHT * text.size / X_HEIGHT
            placed, length = layout(text.text)
            colour = _palette(SOFT_LETTERS) if thing.kind == "hint" else None
            for i, (char, x) in enumerate(placed):
                built = letters[char]
                assert built is not None
                holder = place.attachNewNode(f"letter {i}")
                holder.setPythonTag(
                    "at", ((x - length / 2) * X_HEIGHT * scale, -0.6 * X_HEIGHT * scale)
                )
                holder.setScale(scale)
                piece = built.copyTo(holder)
                if colour is not None:
                    piece.setShaderInput("palette", colour)
                holder.setShaderInput("boil_amount", 0.25)
            self._things[thing.id] = (key, place, place)
        _, place, _ = self._things[thing.id]
        scale = TEXT_XHEIGHT * text.size / X_HEIGHT
        # On the backdrop: the letters' backs just touching it.
        place.setPos(*to_world(thing.position, BACKDROP_DEPTH - ROPE * X_HEIGHT * scale - 0.5))
        for i, holder in enumerate(place.getChildren()):
            x, z = holder.getPythonTag("at")
            j = jitter(thing.id * 131 + i, frame)
            holder.setPos(x + j.dx * LETTER_JITTER, 0, z - j.dy * LETTER_JITTER)
            holder.setR(j.turn * 2)
            holder.setShaderInput("boil_seed", float(frame) + thing.id * 0.618 + i * 1.7)

    def _press(self, thing: Thing, frame: int) -> float:
        """How big the go disc is this frame: it gives a little as the go note goes on."""
        was, since = self._pressed.get(thing.id, (thing.pose, frame - len(GO_PRESS)))
        if thing.pose != was:
            since = frame
        self._pressed[thing.id] = (thing.pose, since)
        step = frame - since
        return GO_PRESS[step] if thing.pose == "on" and step < len(GO_PRESS) else 1.0

    def _bed(self, thing: Thing, place: NodePath, frame: int) -> None:
        """The flower bed's flowers, round its leaves: each a stem and a head, the head one
        of `FLOWER_STAGES` pieces swapped in as it opens. The bed is hidden until all its
        pieces are built, so it never shows half made."""
        r = _radius(thing)
        flowers = self._beds.get(thing.id)
        if flowers is None:
            stems = self._figure(("stem", r), lambda: stem(STEM_LENGTH * r), 0.8, "stem")
            heads = [
                self._figure(
                    ("flower", r, stage),
                    lambda s=stage: flower_head(HEAD_SIZE * r, s),
                    0.6,
                    "flower",
                )
                for stage in range(FLOWER_STAGES)
            ]
            if stems is None or any(head is None for head in heads):
                place.hide()
                self.missing += 1
                return
            flowers = []
            for i, flower in enumerate(FLOWERS):
                holder = place.attachNewNode(f"flower {i}")
                holder.setPos(flower.across * r, flower.depth, -r)  # its foot on the ground
                held_stem = stems.copyTo(holder)
                head = holder.attachNewNode("head")
                colours = _palette(PETALS[flower.colour], CENTRES[flower.colour])
                stages = []
                for built in heads:
                    assert built is not None
                    piece = built.copyTo(head)
                    piece.setShaderInput("palette", colours)
                    piece.hide()
                    stages.append(piece)
                holder.setShaderInput("boil_amount", 0.4)
                flowers.append((holder, held_stem, head, stages))
            self._beds[thing.id] = flowers
            place.show()
        if thing.pose == "won":
            bloomed: int | None = self._bloomed.setdefault(thing.id, frame)
        else:
            bloomed = self._bloomed.pop(thing.id, None) and None
        for i, (flower, (holder, held_stem, head, stages)) in enumerate(
            zip(FLOWERS, flowers, strict=True)
        ):
            state = flower_state(i, frame, bloomed)
            if state.scale <= 0:
                holder.hide()
                continue
            holder.show()
            height = flower.stem * r * state.stem
            held_stem.setScale(1, 1, flower.stem * state.stem / STEM_LENGTH)
            head.setPos(0, -2, height)  # a touch in front of the stem's top
            head.setR(state.sway)
            head.setScale(flower.size / HEAD_SIZE * state.scale)
            for stage, piece in enumerate(stages):
                piece.show() if stage == state.stage else piece.hide()
            holder.setShaderInput("boil_seed", float(frame) + thing.id * 0.618 + i * 3.1)

    def _broken_pieces(self, thing: Thing) -> dict[str, NodePath | None]:
        """A broken egg's figures (bottom half, top half, puddle), each None until built."""
        r = _radius(thing)
        pieces: dict[str, NodePath | None] = {
            "bottom": self._figure(
                ("egg", r, "broken"), lambda: BROKEN_EGG.figure(thing), BROKEN_EGG.step, "egg"
            )
        }
        for name, (recipe, step) in BROKEN_PIECES.items():
            pieces[name] = self._figure(
                ("egg", r, name), lambda recipe=recipe: recipe(r), step, f"egg {name}"
            )
        return pieces

    def _breaking(self, thing: Thing, place: NodePath, frame: int, since: int) -> None:
        """The broken egg's top half and puddle, round its bottom half, posed for `since`
        stop-motion frames after the break (`breaking.py`). Hidden until all its pieces are
        built, so it never shows half made."""
        r = _radius(thing)
        parts = self._breaks.get(thing.id)
        if parts is None:
            pieces = self._broken_pieces(thing)
            top, spill = pieces["top"], pieces["puddle"]
            if top is None or spill is None:
                place.hide()
                self.missing += 1
                return
            lid = place.attachNewNode("top half")
            top.copyTo(lid)
            pool = place.attachNewNode("puddle")
            pool.setPos(0.3 * r, -0.05 * r, -r)  # on the ground, spreading to the right
            spill.copyTo(pool)
            for node in (lid, pool):
                node.setShaderInput("boil_amount", 0.3)
            parts = self._breaks[thing.id] = (lid, pool)
            place.show()
        lid, pool = parts
        lid.setMat(_panda(top_half(r, since)))
        spread = puddle(since)
        if spread <= 0:
            pool.hide()
        else:
            pool.show()
            pool.setScale(spread, 1.0, 1.0)  # it spreads out along the ground
        for i, node in enumerate((lid, pool)):
            node.setShaderInput("boil_seed", float(frame) + thing.id * 0.618 + i * 2.3)

    def _note(self, thing: Thing, frame: int) -> None:
        """A stuck-down note's shadow box and rope, made when it's first seen (or reshaped).
        The box stays exactly with the paper; the rope jitters and boils like a figure."""
        key = ("note", _outline(thing))
        known = self._things.get(thing.id)
        if known is None or known[0] != key:
            if known is not None:
                known[1].removeNode()
            place = self.things.attachNewNode(f"note {thing.id}")
            shadow_box(_outline(thing), BACKDROP_DEPTH).reparentTo(place)
            outline = figure_node(rope(_outline(thing), seed=thing.id % 1000), "note rope")
            outline.reparentTo(place)
            outline.setShaderInput("boil_amount", NOTE_BOIL)
            self._things[thing.id] = (key, place, outline)
        _, place, outline = self._things[thing.id]
        place.setPos(*to_world(thing.position))
        place.setR(heading(thing.angle))
        j = jitter(thing.id, frame)
        outline.setPos(j.dx * NOTE_JITTER, 0, -j.dy * NOTE_JITTER)
        outline.setShaderInput("boil_seed", float(frame) + thing.id * 0.618)


def _lowest_per_degree(mesh: ClayMesh | Packed) -> np.ndarray:
    """How far below its middle a figure reaches when turned by each whole degree in the
    wall's plane (as `NodePath.setR` turns it): for resting the egg on its lowest point."""
    points = mesh.rows[:, :3] if isinstance(mesh, Packed) else mesh.positions
    ups = []
    for degrees in range(360):
        m = TransformState.makeHpr((0, 0, degrees)).getMat()
        ups.append([m.getCell(row, 2) for row in range(3)])  # where z comes from, per axis
    return (np.asarray(points, dtype=np.float64) @ np.array(ups).T).min(axis=0)


def _palette(*colours: tuple[int, int, int]) -> PTA_LVecBase3f:
    """Clay colours for a figure's clays, in its order (see `Figure.clay_names`)."""
    palette = PTA_LVecBase3f.emptyArray(MAX_CLAYS)
    for i in range(MAX_CLAYS):
        palette[i] = tuple(float(c) for c in linear(colours[i])) if i < len(colours) else (1, 1, 1)
    return palette


def _panda(m: np.ndarray) -> LMatrix4f:
    """A 4x4 matrix for column vectors (numpy's way) as Panda3D wants it for `setMat`: it
    works with row vectors, so it's the transpose."""
    return LMatrix4f(*np.asarray(m, dtype=np.float64).T.flatten())
