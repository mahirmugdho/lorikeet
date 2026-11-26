"""Level files: `levels/<id>.json`, in board pixels (320 x 180, y down)."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

BOARD_W = 320
BOARD_H = 180
PAD_TOP = 160  # the bottom strip is the note pad, not playfield

LEVELS_DIR = Path(__file__).parent / "levels"
SUPPORTED_COLORS = ("sun",)  # the other four powers arrive after the prototype review


@dataclass(frozen=True)
class Rect:
    x: int
    y: int
    w: int
    h: int


@dataclass(frozen=True)
class Level:
    id: str
    name: str
    nest: tuple[int, int]  # Lori's starting centre
    nudge: tuple[float, float]  # her velocity when dropped, px/s
    blossom: tuple[int, int]
    terrain: tuple[Rect, ...]
    pad: tuple[tuple[str, int], ...]  # (note colour, count)
    par: int
    timeout_s: float = 10.0
    # A layout known to win, as (colour, x, y, angle). Tests replay it, so tuning can't break it.
    solution: tuple[tuple[str, int, int, int], ...] = ()


def parse_level(data: dict[str, Any], level_id: str) -> Level:
    """Build a Level from parsed JSON, rejecting anything off the board or not yet supported."""

    def point(key: str) -> tuple[int, int]:
        x, y = (int(v) for v in data[key])
        if not (0 <= x < BOARD_W and 0 <= y < PAD_TOP):
            raise ValueError(f"{level_id}: {key} {x},{y} is outside the playfield")
        return x, y

    pad = tuple((str(color), int(count)) for color, count in data["pad"].items())
    for color, count in pad:
        if color not in SUPPORTED_COLORS:
            raise ValueError(f"{level_id}: note colour {color!r} isn't playable yet")
        if count < 1:
            raise ValueError(f"{level_id}: pad needs at least one {color} note")
    nx, ny = data.get("nudge", (0, 0))
    return Level(
        id=level_id,
        name=str(data["name"]),
        nest=point("nest"),
        nudge=(float(nx), float(ny)),
        blossom=point("blossom"),
        terrain=tuple(Rect(*(int(v) for v in r)) for r in data["terrain"]),
        pad=pad,
        par=int(data["par"]),
        timeout_s=float(data.get("timeout_s", 10.0)),
        solution=tuple((str(c), int(x), int(y), int(a)) for c, x, y, a in data.get("solution", ())),
    )


def load_level(level_id: str) -> Level:
    path = LEVELS_DIR / f"{level_id}.json"
    return parse_level(json.loads(path.read_text()), level_id)
