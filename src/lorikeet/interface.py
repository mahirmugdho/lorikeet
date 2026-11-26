"""The contract between Lorikeet's vision code and its games (ADR 0004).

Each camera frame, the vision code turns what it sees into a `Scene`: every sticky piece
on the surface, in projector pixels (ADR 0005). Games read scenes from a `SceneSource` and
decide what a piece means: a wall for a ball to bounce off, or a tower on a grid. Games
that want events instead of snapshots call `changes()`.

This module uses only the standard library, so a game needs nothing from the vision code,
OpenCV, or numpy. Changes here need review from both lanes (docs/workflow.md).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum
from typing import Protocol

Point = tuple[float, float]
"""(x, y) in projector pixels: x grows to the right, y grows downward."""

Polygon = tuple[Point, ...]
"""Corners in order around the edge, in either direction, without repeating the first."""


class PieceState(Enum):
    """The part of a piece's life that games see.

    Tracking has two more states that never reach games: a blob it hasn't confirmed yet
    (so the motion blur of a projected ball never becomes a piece), and a piece that's
    gone for good, which just drops out of the scene.
    """

    MOVING = "moving"
    """Seen this frame and still shifting: just stuck down, or a hand is adjusting it."""

    SETTLED = "settled"
    """Held still long enough to count as placed. A settled piece never changes: if it
    moves, it ends, and a new piece with a new id starts where it lands."""

    HIDDEN = "hidden"
    """A settled piece the camera can't see right now, probably because a hand is in the
    way. It keeps its last outline for `LORIKEET_HIDDEN_SECONDS` (2 by default), then it's
    gone. A piece that vanishes while MOVING is dropped at once, with no grace period."""


_PLACED = frozenset({PieceState.SETTLED, PieceState.HIDDEN})


@dataclass(frozen=True)
class Piece:
    """One solid-coloured sticky thing on the surface, such as a Post-it, or several
    touching ones that detection merged into one piece."""

    id: int
    """Stable for the piece's whole life, and never reused for a later piece."""

    color: str
    """The name of the configured colour it matched, such as "yellow". Colours are set up
    per room (`LORIKEET_PIECE_COLORS`), so treat this as a label, not a fixed list."""

    state: PieceState

    outline: Polygon
    """The piece's true shape, for drawing and hit tests. It can be concave, such as an L
    of three notes."""

    parts: tuple[Polygon, ...]
    """Convex polygons that together cover the outline, for physics engines, which only
    take convex shapes. A single note is one part."""

    def __post_init__(self) -> None:
        _check_shape(self.outline, "outline")
        if not self.parts:
            raise ValueError("a piece needs at least one part")
        for part in self.parts:
            _check_shape(part, "part")
            if not _turns_one_way(part):
                raise ValueError(f"parts must be convex, got {part}")

    @property
    def center(self) -> Point:
        """The outline's balance point (area centroid), not the average of its corners."""
        twice_area = cx = cy = 0.0
        for (x0, y0), (x1, y1) in _edges(self.outline):
            cross = x0 * y1 - x1 * y0
            twice_area += cross
            cx += (x0 + x1) * cross
            cy += (y0 + y1) * cross
        return (cx / (3 * twice_area), cy / (3 * twice_area))


@dataclass(frozen=True)
class Scene:
    """Every piece the camera saw in one frame."""

    time: float
    """When the camera captured the frame, in seconds on a monotonic clock. Only the
    difference between two scenes' times means anything."""

    pieces: tuple[Piece, ...] = ()

    def __post_init__(self) -> None:
        ids = [piece.id for piece in self.pieces]
        repeated = sorted({i for i in ids if ids.count(i) > 1})
        if repeated:
            raise ValueError(f"piece ids must be unique in a scene, repeated: {repeated}")


class SceneSource(Protocol):
    """Where a game gets scenes: the live camera pipeline, or `FakeSceneSource` in tests."""

    def latest(self) -> Scene:
        """The newest scene. It never waits for the camera: if no new frame has arrived,
        it returns the same scene again. Before the first frame, the scene is empty."""
        ...


@dataclass(frozen=True)
class Changes:
    """What `changes()` found between two scenes."""

    placed: tuple[Piece, ...] = ()
    """Pieces that just became placed, as they look now."""

    removed: tuple[Piece, ...] = ()
    """Pieces that are gone for good, as they last looked."""


def changes(before: Scene, after: Scene) -> Changes:
    """The pieces placed and removed between two scenes, for games that want events.

    A piece counts as placed while it's SETTLED or HIDDEN, so a hand passing over a piece
    changes nothing, and a piece that never settled is never placed or removed. There's
    no "moved" event: a moved piece gets a new id, so it's removed and a new one placed.

    The scenes don't have to be consecutive. A game that skipped frames still hears about
    every change between them, except a piece that came and went entirely in between.
    """
    was = {piece.id for piece in before.pieces if piece.state in _PLACED}
    now = {piece.id for piece in after.pieces if piece.state in _PLACED}
    new_ids, gone_ids = now - was, was - now
    return Changes(
        placed=tuple(piece for piece in after.pieces if piece.id in new_ids),
        removed=tuple(piece for piece in before.pieces if piece.id in gone_ids),
    )


class FakeSceneSource:
    """A scripted `SceneSource` for tests. Each `latest()` call returns the next scene, as
    if the camera had delivered a new frame; after the last one, it keeps returning that."""

    def __init__(self, scenes: Iterable[Scene]) -> None:
        self._scenes = list(scenes)
        self._next = 0

    def latest(self) -> Scene:
        if not self._scenes:
            return Scene(time=0.0)
        scene = self._scenes[self._next]
        self._next = min(self._next + 1, len(self._scenes) - 1)
        return scene


def square(center: Point, size: float) -> Polygon:
    """An axis-aligned square for writing test scenes: corners clockwise on screen,
    starting at the top left."""
    x, y = center
    half = size / 2
    return ((x - half, y - half), (x + half, y - half), (x + half, y + half), (x - half, y + half))


def _edges(polygon: Polygon) -> Iterable[tuple[Point, Point]]:
    return zip(polygon, polygon[1:] + polygon[:1], strict=True)


def _check_shape(polygon: Polygon, what: str) -> None:
    if len(polygon) < 3:
        raise ValueError(f"{what} needs at least 3 points, got {len(polygon)}")
    twice_area = sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in _edges(polygon))
    if abs(twice_area) < 1e-9:
        raise ValueError(f"{what} has no area: {polygon}")


def _turns_one_way(polygon: Polygon) -> bool:
    """True if every corner turns the same way (straight corners allowed), which is how a
    convex polygon's edge goes. It doesn't catch a star whose edges cross each other."""
    turns = [
        (bx - ax) * (cy - by) - (by - ay) * (cx - bx)
        for (ax, ay), (bx, by), (cx, cy) in zip(
            polygon, polygon[1:] + polygon[:1], polygon[2:] + polygon[:2], strict=True
        )
    ]
    return all(turn >= 0 for turn in turns) or all(turn <= 0 for turn in turns)
