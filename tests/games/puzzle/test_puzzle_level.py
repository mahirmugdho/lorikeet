"""Level files load, and bad ones are rejected with a clear message."""

import json

import pytest

from lorikeet.games.puzzle.level import BOARD_W, LEVELS_DIR, PAD_TOP, load_level, parse_level

LEVEL_IDS = sorted(p.stem for p in LEVELS_DIR.glob("*.json"))


def base() -> dict[str, object]:
    return json.loads((LEVELS_DIR / "1-1.json").read_text())


@pytest.mark.parametrize("level_id", LEVEL_IDS)
def test_level_loads_on_the_board(level_id: str) -> None:
    level = load_level(level_id)
    for r in level.terrain:
        assert r.x >= 0
        assert r.x + r.w <= BOARD_W
        assert r.y >= 0
        assert r.y + r.h <= PAD_TOP
    assert sum(n for _, n in level.pad) >= level.par


def test_rejects_points_off_the_playfield() -> None:
    data = base()
    data["blossom"] = [100, PAD_TOP + 4]  # inside the pad strip
    with pytest.raises(ValueError, match="outside the playfield"):
        parse_level(data, "bad")


def test_rejects_note_colours_not_built_yet() -> None:
    data = base()
    data["pad"] = {"dusk": 1}
    with pytest.raises(ValueError, match="isn't playable yet"):
        parse_level(data, "bad")
