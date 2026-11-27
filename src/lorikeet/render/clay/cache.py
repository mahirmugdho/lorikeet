"""Built meshes, kept on disk so the clay renderer starts in a moment the second time.

Building a figure takes a few seconds (Lori about four), and a level has several. The
result only depends on the recipe, the grid step and the code that builds it, so each
mesh is saved under a fingerprint of all three. Change any of them and the fingerprint
changes, so a stale mesh is never used. The files go in `.lorikeet/clay-cache/`, which git
ignores; deleting the folder is always safe.
"""

from __future__ import annotations

import hashlib
import pickle
from dataclasses import fields
from importlib.resources import files
from pathlib import Path

import numpy as np

from lorikeet.render.clay.figure import ClayMesh, Figure, build

CACHE = Path(".lorikeet") / "clay-cache"
_BUILDERS = ("shapes.py", "mesher.py", "figure.py")
"""The code a mesh depends on, besides its recipe."""


def built(figure: Figure, step: float, folder: Path = CACHE) -> ClayMesh:
    """`build(figure, step)`, from the cache if it's been built before."""
    path = folder / f"{_fingerprint(figure, step)}.npz"
    if path.exists():
        with np.load(path) as saved:
            return ClayMesh(**{f.name: saved[f.name] for f in fields(ClayMesh)})
    mesh = build(figure, step)
    folder.mkdir(parents=True, exist_ok=True)
    partial = path.with_suffix(".partial.npz")
    np.savez(partial, **{f.name: getattr(mesh, f.name) for f in fields(ClayMesh)})
    partial.replace(path)  # all at once, so a half-written file is never read
    return mesh


def _fingerprint(figure: Figure, step: float) -> str:
    digest = hashlib.sha256(pickle.dumps((figure, step)))
    package = files("lorikeet.render.clay")
    for name in _BUILDERS:
        digest.update(package.joinpath(name).read_bytes())
    return digest.hexdigest()[:24]
