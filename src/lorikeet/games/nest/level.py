"""Nest levels: JSON files in `levels/`, played in file-name order.

A level is laid out in projector pixels (ADR 0005) on a canvas of `size`, with y growing
downward. A file looks like this:

    {
      "format": 1,
      "name": "First hop",
      "size": [1920, 1080],
      "note_size": 100,
      "nest":    {"at": [200, 380], "launch": [320, -300]},
      "blossom": {"at": [1700, 590], "radius": 45},
      "go":      {"at": [130, 920], "radius": 70},
      "terrain": [{"box": [0, 420, 520, 60]}, {"polygon": [[600, 700], [900, 640], ...]}],
      "timeout_s": 8,
      "solution": [{"at": [760, 720], "angle": 20}]
    }

- `format` is always 1 for now. A later change to the format gets a new number, so old
  files are never misread.
- `size` is the canvas the level was laid out on.
- `note_size` (optional, 100) is how big a note it expects. Real notes cover more or fewer
  projector pixels depending on how far the projector is from the wall.
- `nest` is where Lori lays eggs, and `launch` is how fast an egg leaves, in pixels a
  second. Negative y is up.
- `blossom` is the goal: an egg that touches it wins.
- `go` is the spot where a note starts the eggs.
- `terrain` is solid ground: boxes as [left, top, width, height], or convex polygons
  (the physics engine only takes convex shapes).
- `timeout_s` (optional, 10): an egg that gets no closer to the blossom for this long has
  stalled.
- `solution` (optional) is notes that beat the level. Tests play it, so a level can't
  quietly become impossible while its numbers are tuned.

Angles are degrees, clockwise on screen, because people type these files. Everything is
checked as it loads, and an unknown key is an error, so a typo fails loudly instead of being
silently ignored.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from importlib import resources
from typing import Any

from lorikeet.interface import Point, Polygon

FORMAT = 1
_PACKAGE = "lorikeet.games.nest"

OnCanvas = Callable[[object, str], Point]
"""Reads a point at a path, and fails if it isn't on the level's canvas."""


class LevelError(ValueError):
    """A level that can't be used. The message names the file and the field."""


@dataclass(frozen=True)
class Nest:
    at: Point
    launch: tuple[float, float]
    """An egg's velocity as it leaves the nest, in pixels a second (negative y is up)."""


@dataclass(frozen=True)
class Spot:
    at: Point
    radius: float


@dataclass(frozen=True)
class PlacedNote:
    """A note stuck on the wall, as a level's solution lists it."""

    at: Point
    angle: float = 0.0
    """Degrees, clockwise on screen."""
    color: str = "yellow"


@dataclass(frozen=True)
class Level:
    name: str
    size: tuple[int, int]
    note_size: float
    nest: Nest
    blossom: Spot
    go: Spot
    terrain: tuple[Polygon, ...]
    """Every piece of ground as a convex polygon: boxes become their four corners."""
    timeout_s: float
    solution: tuple[PlacedNote, ...]


def level_ids() -> list[str]:
    """Every level's id (its file name without `.json`), in the order they're played."""
    folder = resources.files(_PACKAGE) / "levels"
    return sorted(
        entry.name.removesuffix(".json")
        for entry in folder.iterdir()
        if entry.name.endswith(".json")
    )


def load_level(level_id: str) -> Level:
    ids = level_ids()
    if level_id not in ids:
        raise LevelError(f"no level called {level_id!r}; there are: {', '.join(ids)}")
    text = (resources.files(_PACKAGE) / "levels" / f"{level_id}.json").read_text(encoding="utf-8")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as error:
        raise LevelError(f"{level_id}.json: not valid JSON: {error}") from None
    return parse_level(data, source=f"{level_id}.json")


def parse_level(data: object, source: str = "level") -> Level:
    """Check `data` (a level file, already decoded from JSON) and build the Level."""
    try:
        return _parse(data)
    except _Problem as problem:
        raise LevelError(f"{source}: {problem}") from None


class _Problem(Exception):
    """What's wrong, and where: a path like `terrain[2].box`."""

    def __init__(self, path: str, message: str) -> None:
        super().__init__(f"{path}: {message}" if path else message)


def _parse(data: object) -> Level:
    fields = _object(
        data,
        "",
        required={"format", "name", "size", "nest", "blossom", "go", "terrain"},
        optional={"note_size", "timeout_s", "solution"},
    )
    if fields["format"] != FORMAT:
        raise _Problem("format", f"expected {FORMAT}, got {fields['format']!r}")
    width, height = size = _size(fields["size"], "size")

    def on_canvas(value: object, path: str) -> Point:
        x, y = point = _point(value, path)
        if not (0 <= x <= width and 0 <= y <= height):
            raise _Problem(path, f"{point} is off the {width}x{height} canvas")
        return point

    nest = _object(fields["nest"], "nest", required={"at", "launch"})
    pieces = _list(fields["terrain"], "terrain")
    notes = _list(fields.get("solution", []), "solution")
    return Level(
        name=_text(fields["name"], "name"),
        size=size,
        note_size=_positive(fields.get("note_size", 100), "note_size"),
        nest=Nest(
            at=on_canvas(nest["at"], "nest.at"), launch=_point(nest["launch"], "nest.launch")
        ),
        blossom=_spot(fields["blossom"], "blossom", on_canvas),
        go=_spot(fields["go"], "go", on_canvas),
        terrain=tuple(_terrain(piece, f"terrain[{i}]") for i, piece in enumerate(pieces)),
        timeout_s=_positive(fields.get("timeout_s", 10), "timeout_s"),
        solution=tuple(_note(note, f"solution[{i}]", on_canvas) for i, note in enumerate(notes)),
    )


def _spot(value: object, path: str, on_canvas: OnCanvas) -> Spot:
    fields = _object(value, path, required={"at", "radius"})
    return Spot(
        at=on_canvas(fields["at"], f"{path}.at"),
        radius=_positive(fields["radius"], f"{path}.radius"),
    )


def _note(value: object, path: str, on_canvas: OnCanvas) -> PlacedNote:
    fields = _object(value, path, required={"at"}, optional={"angle", "color"})
    return PlacedNote(
        at=on_canvas(fields["at"], f"{path}.at"),
        angle=_number(fields.get("angle", 0), f"{path}.angle"),
        color=_text(fields.get("color", "yellow"), f"{path}.color"),
    )


def _terrain(value: object, path: str) -> Polygon:
    piece = _object(value, path, required=set(), optional={"box", "polygon"})
    if len(piece) != 1:
        raise _Problem(path, "needs exactly one of 'box' or 'polygon'")
    if "box" in piece:
        box = piece["box"]
        if not isinstance(box, list) or len(box) != 4:
            raise _Problem(f"{path}.box", "expected [left, top, width, height]")
        left, top, w, h = (_number(n, f"{path}.box") for n in box)
        if w <= 0 or h <= 0:
            raise _Problem(f"{path}.box", "width and height must be positive")
        return ((left, top), (left + w, top), (left + w, top + h), (left, top + h))
    points = _list(piece["polygon"], f"{path}.polygon")
    polygon = tuple(_point(point, f"{path}.polygon[{i}]") for i, point in enumerate(points))
    if len(polygon) < 3 or not _convex(polygon):
        raise _Problem(f"{path}.polygon", "must be convex with at least 3 corners")
    return polygon


def _convex(polygon: Polygon) -> bool:
    """True if every corner turns the same way and the polygon has area: walking round a
    convex polygon, you always turn left, or always right."""
    turns = [
        (bx - ax) * (cy - by) - (by - ay) * (cx - bx)
        for (ax, ay), (bx, by), (cx, cy) in zip(
            polygon, polygon[1:] + polygon[:1], polygon[2:] + polygon[:2], strict=True
        )
    ]
    one_way = all(t >= 0 for t in turns) or all(t <= 0 for t in turns)
    return one_way and any(t != 0 for t in turns)


def _object(
    value: object, path: str, required: set[str], optional: frozenset[str] | set[str] = frozenset()
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise _Problem(path, "expected an object, like {...}")
    unknown = sorted(set(value) - required - set(optional))
    if unknown:
        allowed = ", ".join(sorted(required | set(optional)))
        raise _Problem(path, f"unknown key {unknown[0]!r} (allowed: {allowed})")
    missing = sorted(required - set(value))
    if missing:
        raise _Problem(path, f"missing key {missing[0]!r}")
    return value


def _list(value: object, path: str) -> list[Any]:
    if not isinstance(value, list):
        raise _Problem(path, "expected a list, like [...]")
    return value


def _number(value: object, path: str) -> float:
    # bool is a kind of int in Python, but `true` is never a sensible number in a level.
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise _Problem(path, f"expected a number, got {value!r}")
    return float(value)


def _positive(value: object, path: str) -> float:
    number = _number(value, path)
    if number <= 0:
        raise _Problem(path, f"must be positive, got {number:g}")
    return number


def _point(value: object, path: str) -> Point:
    if not isinstance(value, list) or len(value) != 2:
        raise _Problem(path, f"expected [x, y], got {value!r}")
    return (_number(value[0], path), _number(value[1], path))


def _size(value: object, path: str) -> tuple[int, int]:
    if (
        not isinstance(value, list)
        or len(value) != 2
        or not all(isinstance(n, int) and not isinstance(n, bool) and n > 0 for n in value)
    ):
        raise _Problem(path, f"expected [width, height] in whole pixels, got {value!r}")
    return (value[0], value[1])


def _text(value: object, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _Problem(path, f"expected some text, got {value!r}")
    return value
