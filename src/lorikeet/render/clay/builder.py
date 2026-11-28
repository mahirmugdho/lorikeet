"""Building figures without stalling the game.

The first time a figure is needed it has to be built, which takes seconds (Lori about six),
or read back from the disk cache (`cache.py`), which takes a moment. A game can't wait that
long in the middle of a frame: the first egg would freeze everything. So `Builder` builds in
other processes, and the clay set leaves a thing out until its figure is ready, then puts it
in. With a warm cache that's a frame or two; the first run after a recipe changes fills the
set in over a few seconds.

Processes, not threads: building is mostly numpy, but enough of it is plain Python that a
thread would hold up the game's own Python (physics, the desk) while it ran. The workers are
also kept from crowding out the game for the computer's cores: each does its maths on one
core, and at a low priority, so the game's frames always come first.
"""

from __future__ import annotations

import multiprocessing
import os
import signal
from collections.abc import Callable, Hashable
from concurrent.futures import Future, ProcessPoolExecutor
from typing import Protocol

from lorikeet.render.clay.cache import built
from lorikeet.render.clay.figure import ClayMesh, Figure, Packed, pack


class Builds(Protocol):
    def mesh(
        self, key: Hashable, figure: Callable[[], Figure], step: float
    ) -> ClayMesh | Packed | None:
        """The mesh for `key` if it's ready, or None while it's still being built. The recipe
        (`figure`) is only made if it's needed."""
        ...


class Builder:
    def __init__(self, workers: int | None = None) -> None:
        """`workers` processes build at once: by default as many as the computer has cores
        to spare, up to four."""
        if workers is None:
            workers = max(1, min(4, (os.cpu_count() or 2) - 2))
        # "spawn" starts each worker fresh, rather than as a copy of this process with its
        # windows and graphics driver open, which a copy can't safely share.
        context = multiprocessing.get_context("spawn")
        # numpy's maths library starts a thread per core in each process, which would crowd
        # the game out. Workers started from here on read this when they load numpy.
        for setting in _ONE_THREAD:
            os.environ.setdefault(setting, "1")
        self._pool = ProcessPoolExecutor(workers, mp_context=context, initializer=_step_back)
        self._jobs: dict[Hashable, Future[Packed]] = {}

    def mesh(self, key: Hashable, figure: Callable[[], Figure], step: float) -> Packed | None:
        """Ready packed for the graphics card (`figure.pack`), so the game's process only
        has to copy it."""
        job = self._jobs.get(key)
        if job is None:
            job = self._jobs[key] = self._pool.submit(_built_and_packed, figure(), step)
        if not job.done():
            return None
        del self._jobs[key]  # handed over: the caller keeps the figure from now on
        return job.result()  # a failed build raises here, rather than vanishing

    def close(self) -> None:
        self._pool.shutdown(wait=False, cancel_futures=True)


_ONE_THREAD = ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS")


def _built_and_packed(figure: Figure, step: float) -> Packed:
    return pack(built(figure, step))


def _step_back() -> None:
    """In each worker: run at a low priority, so the game's own frames come first, and leave
    Ctrl-C to the game, which shuts the workers down itself."""
    if hasattr(os, "nice"):
        os.nice(10)
    signal.signal(signal.SIGINT, signal.SIG_IGN)


class BuildNow:
    """Builds on the spot, waiting as long as it takes: for offscreen tools and tests."""

    def __init__(self, build: Callable[[Figure, float], ClayMesh] = built) -> None:
        self._build = build

    def mesh(self, key: Hashable, figure: Callable[[], Figure], step: float) -> ClayMesh | None:
        return self._build(figure(), step)
