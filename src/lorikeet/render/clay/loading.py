"""When the clay set has loaded, so it can be shown all at once.

At startup the set's figures arrive over a few frames (a fraction of a second when they're
cached on disk, several seconds the first time after the clay code changes: `builder.py`).
Shown as they came, things would pop in one by one. So the set is held out of sight (only
the backdrop shows) until everything in the game's View is on it, then shown together.
If that takes long enough to notice, "Loading…" is written in the middle meanwhile.

Only at startup: things the game first shows later (the first egg) can't be known ahead.
"""

from __future__ import annotations

from dataclasses import dataclass, field

WORDS = "Loading…"

QUIET = 1.0
"""Seconds before "Loading…" appears: a load quicker than this (a cached one takes about
half a second, counting the first frame's shader compiling) just looks like the set
appearing, with no word flashing up and away."""

LIMIT = 30.0
"""Seconds after which the set is shown however much is still missing, so nothing can hold
the game hidden for good."""


@dataclass
class Loading:
    started: float
    """When the renderer started, in seconds on the same clock as `step`'s `now`."""
    done: bool = field(default=False, init=False)

    def step(self, missing: int, now: float) -> tuple[bool, bool]:
        """Given how many things aren't on the set yet: whether to keep holding the set out
        of sight, and whether to write "Loading…". Once it's done, it stays done."""
        waited = now - self.started
        if not self.done and (missing == 0 or waited >= LIMIT):
            self.done = True
        if self.done:
            return False, False
        return True, waited >= QUIET
