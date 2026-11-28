"""Nest levels are JSON files in projector pixels, checked strictly as they load."""

import copy
from typing import Any

import pytest

from lorikeet.games.nest.level import LevelError, PlacedNote, level_ids, load_level, parse_level

MINIMAL: dict[str, Any] = {
    "format": 1,
    "name": "Test",
    "size": [1920, 1080],
    "nest": {"at": [200, 380], "launch": [300, -250]},
    "blossom": {"at": [1700, 590], "radius": 45},
    "go": {"at": [130, 920], "radius": 70},
    "terrain": [{"box": [0, 420, 520, 60]}],
}


def level(**changes: Any) -> dict[str, Any]:
    """The minimal level with some fields replaced."""
    data = copy.deepcopy(MINIMAL)
    data.update(changes)
    return data


def without(key: str) -> dict[str, Any]:
    data = copy.deepcopy(MINIMAL)
    del data[key]
    return data


def test_every_shipped_level_loads():
    assert [load_level(level_id).name for level_id in level_ids()]


def test_levels_are_played_in_file_name_order_starting_with_first_hop():
    assert level_ids()[0] == "01-first-hop"


def test_a_box_becomes_its_four_corners_clockwise_from_the_top_left():
    assert parse_level(MINIMAL).terrain == (((0, 420), (520, 420), (520, 480), (0, 480)),)


def test_a_convex_polygon_is_kept_as_given():
    ramp = [[600, 700], [900, 640], [900, 660], [600, 720]]

    terrain = parse_level(level(terrain=[{"polygon": ramp}])).terrain

    assert terrain == (((600, 700), (900, 640), (900, 660), (600, 720)),)


def test_optional_fields_have_defaults():
    loaded = parse_level(MINIMAL)

    assert (loaded.timeout_s, loaded.note_size, loaded.solution) == (10.0, 100.0, ())


def test_a_solution_note_is_unturned_and_yellow_unless_it_says_otherwise():
    loaded = parse_level(level(solution=[{"at": [760, 720]}]))

    assert loaded.solution == (PlacedNote(at=(760, 720), angle=0.0, color="yellow"),)


def test_an_unknown_key_is_rejected_so_a_typo_fails_loudly():
    with pytest.raises(LevelError, match="blosom"):
        parse_level(level(blosom={"at": [1700, 590], "radius": 45}))


def test_a_missing_key_is_rejected():
    with pytest.raises(LevelError, match="go"):
        parse_level(without("go"))


def test_only_format_1_is_understood():
    with pytest.raises(LevelError, match="format"):
        parse_level(level(format=2))


def test_spots_must_be_on_the_canvas():
    with pytest.raises(LevelError, match=r"blossom\.at"):
        parse_level(level(blossom={"at": [2000, 590], "radius": 45}))


def test_a_radius_must_be_positive():
    with pytest.raises(LevelError, match=r"go\.radius"):
        parse_level(level(go={"at": [130, 920], "radius": 0}))


def test_a_box_needs_a_positive_size():
    with pytest.raises(LevelError, match=r"terrain\[0\]\.box"):
        parse_level(level(terrain=[{"box": [0, 420, 0, 60]}]))


def test_a_terrain_piece_is_a_box_or_a_polygon():
    with pytest.raises(LevelError, match=r"terrain\[0\]"):
        parse_level(level(terrain=[{"circle": [100, 100, 50]}]))


def test_a_polygon_must_be_convex():
    # Physics takes only convex shapes. This arrowhead dents inwards at (650, 650).
    arrowhead = [[600, 600], [700, 600], [650, 650], [700, 700], [600, 700]]

    with pytest.raises(LevelError, match="convex"):
        parse_level(level(terrain=[{"polygon": arrowhead}]))


def test_numbers_must_be_numbers():
    with pytest.raises(LevelError, match=r"nest\.launch"):
        parse_level(level(nest={"at": [200, 380], "launch": ["fast", 0]}))


def test_loading_a_level_that_does_not_exist_says_so():
    with pytest.raises(LevelError, match="no level called 'nope'"):
        load_level("nope")
