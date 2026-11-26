"""Simulated notes: a `SceneSource` you stick notes onto in code (and, later, with a mouse).

It stands in for the camera pipeline, so it follows the rules that pipeline will follow
(ADR 0004). A sim that's kinder than the real wall makes games that only work on a laptop:

- A dropped note is MOVING until it has held still for `settle_seconds`, then SETTLED.
- There's no way to slide a note. Moving one means picking it up and dropping it again,
  because that's what the camera sees, so it comes back as a new piece with a new id.
- Picking up a SETTLED note doesn't remove it at once. Tracking can't tell a peeled note
  from one behind a hand, so the note stays HIDDEN for `hidden_seconds` first. A note
  picked up while still MOVING disappears at once, with no grace period.

Not simulated yet: touching notes of one colour merging into one piece, the short wait
before tracking confirms a new blob, and camera noise (jitter, dropouts, colour misreads).
"""

from __future__ import annotations

import math
import time
from collections.abc import Callable
from dataclasses import dataclass

from lorikeet.interface import Piece, PieceState, Point, Polygon, Scene


@dataclass
class _Note:
    color: str
    outline: Polygon
    dropped_at: float
    lifted_at: float | None = None
    """When it was picked up, if it has been: it's HIDDEN until the grace period ends."""


class SimSceneSource:
    """Simulated notes on the surface, in projector pixels.

    The defaults match `LORIKEET_SETTLE_SECONDS` and `LORIKEET_HIDDEN_SECONDS` in
    `.env.example`. `clock` must be monotonic, and tests pass a fake one so every
    timing is exact.
    """

    def __init__(
        self,
        *,
        note_size: float = 100.0,
        settle_seconds: float = 0.2,
        hidden_seconds: float = 2.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if note_size <= 0:
            raise ValueError(f"note_size must be positive, got {note_size}")
        self.note_size = note_size
        self._settle_seconds = settle_seconds
        self._hidden_seconds = hidden_seconds
        self._clock = clock
        self._notes: dict[int, _Note] = {}
        self._next_id = 1

    def drop(self, color: str, center: Point, angle: float = 0.0) -> int:
        """Stick a note down centred on `center`, turned `angle` degrees clockwise on
        screen. Returns the id its piece has in every scene from now on."""
        note_id = self._next_id
        self._next_id += 1  # ids only ever count up, so one is never reused
        outline = _turned_square(center, self.note_size, angle)
        self._notes[note_id] = _Note(color, outline, dropped_at=self._clock())
        return note_id

    def pick_up(self, note_id: int) -> None:
        """Peel a note off the surface. Raises `KeyError` if it isn't on the surface."""
        note = self._notes.get(note_id)
        if note is None or note.lifted_at is not None:
            raise KeyError(note_id)
        now = self._clock()
        if self._state(note, now) is PieceState.MOVING:
            del self._notes[note_id]
        else:
            note.lifted_at = now

    def latest(self) -> Scene:
        now = self._clock()
        pieces: list[Piece] = []
        for note_id, note in list(self._notes.items()):
            state = self._state(note, now)
            if state is None:
                del self._notes[note_id]  # its grace period is over: gone for good
                continue
            # A square is convex, so the whole outline is the note's only part.
            parts = (note.outline,)
            pieces.append(Piece(note_id, note.color, state, note.outline, parts))
        return Scene(time=now, pieces=tuple(pieces))

    def _state(self, note: _Note, now: float) -> PieceState | None:
        """The state games see at `now`, or None once the note is gone."""
        if note.lifted_at is not None:
            hidden_for = now - note.lifted_at
            return PieceState.HIDDEN if hidden_for < self._hidden_seconds else None
        if now - note.dropped_at >= self._settle_seconds:
            return PieceState.SETTLED
        return PieceState.MOVING


def _turned_square(center: Point, size: float, angle: float) -> Polygon:
    """A square's corners, clockwise on screen from the top left like `interface.square`,
    turned `angle` degrees about its centre.

    This is the usual rotation formula. Because y grows downward on screen, it turns
    corners clockwise, not counter-clockwise as on a maths graph.
    """
    cx, cy = center
    half = size / 2
    cos, sin = math.cos(math.radians(angle)), math.sin(math.radians(angle))
    corners = ((-half, -half), (half, -half), (half, half), (-half, half))
    return tuple((cx + dx * cos - dy * sin, cy + dx * sin + dy * cos) for dx, dy in corners)
