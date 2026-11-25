"""Prototype screens: title -> build -> play -> won or poof -> build.

The game advances in fixed 1/120 s ticks: one physics step and one animation tick each. On the
projector the camera will supply the notes; until then the mouse and the pad stand in.
"""

import math
from dataclasses import dataclass, replace
from enum import Enum, auto

import pygame

from .level import PAD_TOP, Level
from .sim import ROTATE_STEP, Outcome, PlacedNote, Run
from .sprites import EGG_FRAMES

TICKS_PER_SECOND = 120  # one sim step per tick
POP_TICKS = 30  # Lori's squash-and-hop as the egg pops out
POOF_TICKS = 150  # long enough to watch the splat settle
PRESS_TICKS = 10  # a Sun note dips under the egg
NOTE_HALF_W, NOTE_HALF_H = 11, 3
PAD_SLOT_X, PAD_SLOT_Y, PAD_SLOT_GAP = 8, 167, 28
DROP_BUTTON = pygame.Rect(232, 162, 84, 14)


class Mode(Enum):
    TITLE = auto()
    BUILD = auto()
    PLAY = auto()
    WON = auto()
    POOF = auto()


@dataclass
class Peel:
    """A spent note fluttering away. Drawing only; the sim already removed it."""

    note: PlacedNote
    x0: float
    y0: float
    side: int  # +1 drifts right, -1 left
    born: int


@dataclass
class Burst:
    """A one-shot effect at a point: "spark" (sparkles), "ring" (shock ring) or "smoke"."""

    x: int
    y: int
    colors: str
    born: int
    kind: str = "spark"


@dataclass
class Splat:
    """Where the egg hit the floor: x, and the floor line it sits on."""

    x: int
    y: int
    born: int


@dataclass(frozen=True)
class Ghost:
    """The path of the last finished run, kept so the next attempt can be planned against it."""

    points: list[tuple[float, float]]
    springs: list[tuple[float, float]]  # where Sun notes bounced it
    end: tuple[float, float]
    outcome: Outcome


PATH_EVERY = 2  # ticks between recorded points of the egg's path
TRAIL_EVERY = 6  # ticks between the egg's trail sparkles
TRAIL_LIFE = 60  # ticks a trail sparkle lasts (half a second: it lingers, then fades)


class Game:
    def __init__(self, level: Level) -> None:
        self.level = level
        self.mode = Mode.TITLE
        self.tick = 0
        self.mode_tick = 0
        self.placed: list[PlacedNote] = []
        self.held: PlacedNote | None = None
        self.last_angle = 0
        self.cursor = (0, 0)  # board pixels: where a note lands
        self.pointer = (0, 0)  # window pixels: where the held note is drawn, smoothly
        self.run: Run | None = None
        self.egg_pos: tuple[float, float] = (float(level.nest[0]), float(level.nest[1]))
        self.egg_frame = 0
        self.press: dict[int, int] = {}  # note index -> tick its dip ends
        self.peels: list[Peel] = []
        self.bursts: list[Burst] = []
        self.trail: list[tuple[int, int, int]] = []  # (x, y, tick) behind the egg
        self.poof_at = (0, 0)
        self.splat: Splat | None = None
        self.result: Outcome | None = None
        self.ghost: Ghost | None = None  # the last finished run's path
        self._path: list[tuple[float, float]] = []
        self._springs: list[tuple[float, float]] = []

    # -- pad --------------------------------------------------------------------------------

    def pad_count(self, color: str) -> int:
        total = dict(self.level.pad).get(color, 0)
        used = sum(n.color == color for n in self.placed)
        held = self.held is not None and self.held.color == color
        return total - used - held

    def pad_slots(self) -> list[tuple[str, pygame.Rect]]:
        slots: list[tuple[str, pygame.Rect]] = []
        for color, _ in self.level.pad:
            for _ in range(self.pad_count(color)):
                x = PAD_SLOT_X + len(slots) * PAD_SLOT_GAP
                slots.append((color, pygame.Rect(x, PAD_SLOT_Y, 22, 7)))
        return slots

    def note_at(self, x: int, y: int) -> int | None:
        """Index of the placed note under (x, y), testing against its rotated box."""
        for i in reversed(range(len(self.placed))):
            n = self.placed[i]
            a = math.radians(n.angle)
            dx, dy = x - n.x, y - n.y
            lx = dx * math.cos(a) + dy * math.sin(a)
            ly = -dx * math.sin(a) + dy * math.cos(a)
            if abs(lx) <= NOTE_HALF_W and abs(ly) <= NOTE_HALF_H:
                return i
        return None

    # -- input ------------------------------------------------------------------------------

    def handle(self, ev: pygame.event.Event, scale: int) -> None:
        if ev.type in (pygame.MOUSEMOTION, pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP):
            self.pointer = (int(ev.pos[0]), int(ev.pos[1]))
            self.cursor = (self.pointer[0] // scale, self.pointer[1] // scale)
        if ev.type == pygame.KEYDOWN:
            if ev.key == pygame.K_r:
                self.reset()
            elif ev.key == pygame.K_SPACE:
                self.advance()
            elif ev.key == pygame.K_q:
                self.rotate(-1)
            elif ev.key == pygame.K_e:
                self.rotate(1)
        elif ev.type == pygame.MOUSEWHEEL:
            self.rotate(1 if ev.y > 0 else -1)
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            self.press_at(*self.cursor)
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 3:
            self.take_back(*self.cursor)
        elif ev.type == pygame.MOUSEBUTTONUP and ev.button == 1:
            self.release(*self.cursor)

    def advance(self) -> None:
        """Space: start from the title, drop in build mode, try again after a win."""
        if self.mode in (Mode.TITLE, Mode.WON):
            self.set_mode(Mode.BUILD)
        elif self.mode is Mode.BUILD:
            self.drop()

    def press_at(self, x: int, y: int) -> None:
        if self.mode is not Mode.BUILD:
            self.advance()
            return
        if DROP_BUTTON.collidepoint(x, y):
            self.drop()
            return
        for color, rect in self.pad_slots():
            if rect.collidepoint(x, y):
                self.held = PlacedNote(color, x, y, self.last_angle)
                return
        i = self.note_at(x, y)
        if i is not None:
            self.held = self.placed.pop(i)

    def release(self, x: int, y: int) -> None:
        if self.mode is not Mode.BUILD or self.held is None:
            return
        if y < PAD_TOP:  # dropping it on the pad puts it back
            self.placed.append(replace(self.held, x=x, y=y))
        self.held = None

    def take_back(self, x: int, y: int) -> None:
        """Right-click: return the held note, or the note under the cursor, to the pad."""
        if self.mode is not Mode.BUILD:
            return
        if self.held is not None:
            self.held = None
            return
        i = self.note_at(x, y)
        if i is not None:
            self.placed.pop(i)

    def rotate(self, direction: int) -> None:
        if self.mode is not Mode.BUILD:
            return
        step = direction * ROTATE_STEP
        if self.held is not None:
            self.held = replace(self.held, angle=(self.held.angle + step) % 360)
            self.last_angle = self.held.angle
            return
        i = self.note_at(*self.cursor)
        if i is not None:
            n = self.placed[i]
            self.placed[i] = replace(n, angle=(n.angle + step) % 360)
            self.last_angle = self.placed[i].angle

    def reset(self) -> None:
        """R: from play, back to build with notes kept. In build, every note goes back."""
        if self.mode is Mode.BUILD:
            self.placed.clear()
            self.held = None
        else:
            self.set_mode(Mode.BUILD)

    def drop(self) -> None:
        self.held = None
        self.run = Run(self.level, self.placed)
        self.press.clear()
        self.peels.clear()
        self.bursts = [Burst(*self.level.nest, "pv", self.tick)]
        self.trail.clear()
        self.egg_pos = (float(self.level.nest[0]), float(self.level.nest[1]))
        self.egg_frame = 0
        self._path = [self.egg_pos]
        self._springs = []
        self.set_mode(Mode.PLAY)

    def set_mode(self, mode: Mode) -> None:
        self.mode = mode
        self.mode_tick = 0
        if mode is Mode.BUILD:
            self.run = None
            self.peels.clear()
            self.bursts.clear()
            self.trail.clear()
            self.splat = None

    # -- ticks ------------------------------------------------------------------------------

    def update(self) -> None:
        """Advance one 1/120 s tick."""
        self.tick += 1
        self.mode_tick += 1
        if self.mode is Mode.PLAY and self.run is not None:
            self._play_tick(self.run)
        if self.mode is Mode.POOF and self.mode_tick >= POOF_TICKS:
            self.set_mode(Mode.BUILD)
        self.peels = [p for p in self.peels if self.tick - p.born < 2 * TICKS_PER_SECOND]
        self.bursts = [b for b in self.bursts if self.tick - b.born < 2 * TICKS_PER_SECOND]
        self.trail = [t for t in self.trail if self.tick - t[2] < TRAIL_LIFE]

    def _play_tick(self, run: Run) -> None:
        outcome = run.step()
        for ev in run.drain_events():
            if ev.kind == "spring":
                self.press[ev.note] = self.tick + PRESS_TICKS
                x, y = run.egg.position
                self._springs.append((x, y))
                self.bursts.append(Burst(int(x), int(y) + 4, "", self.tick, "ring"))
                self.bursts.append(Burst(int(x), int(y) + 4, "yp", self.tick))
            elif ev.kind == "peel":
                n = run.notes[ev.note].note
                side = 1 if run.egg.position.x < n.x else -1
                self.peels.append(Peel(n, float(n.x), float(n.y), side, self.tick))
        p = run.egg.position
        self.egg_pos = (p.x, p.y)
        if self.mode_tick % PATH_EVERY == 0:
            self._path.append(self.egg_pos)
        if outcome is not Outcome.RUNNING:
            if self._path[-1] != self.egg_pos:
                self._path.append(self.egg_pos)
            self.ghost = Ghost(self._path, self._springs, self.egg_pos, outcome)
        if self.tick % TRAIL_EVERY == 0 and run.egg.velocity.length > 30:
            self.trail.append((int(p.x), int(p.y), self.tick))
        self.egg_frame = round(run.egg.angle / (2 * math.pi / EGG_FRAMES)) % EGG_FRAMES
        if outcome is Outcome.WON:
            self.result = outcome
            self.set_mode(Mode.WON)  # the renderer plays the nectar burst from mode_tick 0
        elif outcome is Outcome.SPLAT:
            self.result = outcome
            self.splat = Splat(int(p.x), PAD_TOP, self.tick)
            self.set_mode(Mode.POOF)
        elif outcome in (Outcome.FELL, Outcome.STALLED):
            self.result = outcome
            self.poof_at = (int(min(max(p.x, 8), 312)), int(min(max(p.y, 8), PAD_TOP - 8)))
            self.bursts.append(Burst(*self.poof_at, "", self.tick, "smoke"))
            self.bursts.append(Burst(*self.poof_at, "pv", self.tick))
            self.set_mode(Mode.POOF)
