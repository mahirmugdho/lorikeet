"""When the clay set has loaded, so it can be shown all at once, and how far along it is.

At startup the set's figures arrive over a few frames (a fraction of a second when they're
cached on disk, several seconds the first time after the clay code changes: `builder.py`).
Shown as they came, things would pop in one by one. So the set is held out of sight (only
the backdrop shows) until everything in the game's View is on it, then shown together. If
that takes long enough to notice, the loading screen shows meanwhile (`loading_screen.py`):
"Loading…" and a track filling with clay beads as things arrive.

Only at startup: things the game first shows later (the first egg) can't be known ahead.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from lorikeet.render.clay.loading_art import BEADS

QUIET = 1.0
"""Seconds before the loading screen appears: a load quicker than this (a cached one takes
about half a second, counting the first frame's shader compiling) just looks like the set
appearing, with no screen flashing up and away."""

LIMIT = 30.0
"""Seconds after which the set is shown however much is still missing, so nothing can hold
the game hidden for good."""


@dataclass(frozen=True)
class Progress:
    holding: bool
    """Whether to keep the set out of sight."""
    screen: bool
    """Whether to show the loading screen."""
    beads: int
    """How many of the loading bar's beads to show."""


@dataclass
class Loading:
    started: float
    """When the renderer started, in seconds on the same clock as `step`'s `now`."""
    done: bool = field(default=False, init=False)
    _most: int = field(default=0, init=False)  # the most things ever missing at once
    _beads: int = field(default=0, init=False)

    def step(self, missing: int, now: float, built: float | None = None) -> Progress:
        """Given how many things aren't on the set yet, what to show. Once it's done, it
        stays done. The beads show `built`, the share of the pieces needed that are built
        (from `ClayScene.progress`), or else the share of the most things ever missing at
        once that have arrived since. They only ever go up."""
        waited = now - self.started
        if not self.done and (missing == 0 or waited >= LIMIT):
            self.done = True
        if self.done:
            return Progress(holding=False, screen=False, beads=BEADS)
        self._most = max(self._most, missing, 1)
        arrived = built if built is not None else 1 - missing / self._most
        self._beads = max(self._beads, math.floor(arrived * BEADS))
        return Progress(holding=True, screen=waited >= QUIET, beads=self._beads)
