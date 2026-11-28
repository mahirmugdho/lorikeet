"""What Nest shows each frame, as a View for whichever renderer is drawing (ADR 0008)."""

import math

import pytest

from lorikeet.games.nest.game import LAY_DELAY, NestGame
from lorikeet.games.nest.level import Level, parse_level
from lorikeet.interface import Piece, PieceState, Point, Scene
from lorikeet.view import Circle, Outline, Text, Thing, View

LEVEL: Level = parse_level(
    {
        "format": 1,
        "name": "View test",
        "size": [1000, 600],
        "nest": {"at": [200, 100], "launch": [0, 0]},
        "blossom": {"at": [800, 200], "radius": 40},
        "go": {"at": [900, 550], "radius": 40},
        "terrain": [{"box": [0, 300, 400, 40]}, {"box": [600, 400, 400, 40]}],
    }
)


def note(piece_id: int, center: Point, state: PieceState = PieceState.SETTLED) -> Piece:
    x, y = center
    outline = ((x - 50, y - 50), (x + 50, y - 50), (x + 50, y + 50), (x - 50, y + 50))
    return Piece(id=piece_id, color="yellow", state=state, outline=outline, parts=(outline,))


GO_NOTE = note(99, LEVEL.go.at)


def shown(*pieces: Piece, seconds: float = 0.0) -> View:
    game = NestGame(LEVEL)
    scene = Scene(time=0.0, pieces=pieces)
    game.update(scene, 0.0)
    for _ in range(round(seconds * 120)):
        game.update(scene, 1 / 120)
    return game.view()


def of_kind(view: View, kind: str) -> list[Thing]:
    return [thing for thing in view.things if thing.kind == kind]


def test_each_piece_of_terrain_is_shown_where_it_is():
    terrain = of_kind(shown(), "terrain")

    placed = [t.shape.placed(t.position, t.angle) for t in terrain if isinstance(t.shape, Outline)]
    assert [[pytest.approx(p) for p in polygon] for polygon in placed] == [
        list(polygon) for polygon in LEVEL.terrain
    ]


def test_the_blossom_is_a_circle_at_its_spot():
    (blossom,) = of_kind(shown(), "blossom")

    assert (blossom.position, blossom.shape) == (LEVEL.blossom.at, Circle(LEVEL.blossom.radius))


def test_the_go_spot_is_off_until_a_note_is_on_it():
    (off,) = of_kind(shown(), "go")
    (on,) = of_kind(shown(GO_NOTE), "go")

    assert (off.pose, on.pose) == ("off", "on")


def test_lori_sits_in_her_nest():
    view = shown()
    (nest,), (lori,) = of_kind(view, "nest"), of_kind(view, "bird")

    assert nest.position == LEVEL.nest.at
    assert isinstance(nest.shape, Circle)
    assert math.dist(lori.position, nest.position) < nest.shape.radius  # in it...
    assert lori.position[1] < nest.position[1]  # ...sticking up out of it...
    assert nest.layer > lori.layer  # ...with the nest in front, hiding her lower half


def test_lori_is_laying_while_the_next_egg_is_coming():
    (lori,) = of_kind(shown(GO_NOTE), "bird")

    assert lori.pose == "laying"


def test_there_is_no_egg_until_one_is_laid():
    assert of_kind(shown(), "egg") == []


def test_the_egg_is_shown_where_it_is():
    game = NestGame(LEVEL)
    scene = Scene(time=0.0, pieces=(GO_NOTE,))
    for _ in range(round((LAY_DELAY + 0.5) * 120)):
        game.update(scene, 1 / 120)

    view = game.view()
    (egg,), (nest,) = of_kind(view, "egg"), of_kind(view, "nest")

    assert egg.position == game.egg
    assert egg.layer > nest.layer  # in front, so it's seen coming out of the nest


def test_stuck_down_notes_are_shown_as_notes_and_notes_in_a_hand_are_not():
    view = shown(note(1, (500, 200)), note(2, (300, 450), PieceState.MOVING))

    assert len(of_kind(view, "note")) == 1


def test_the_egg_is_drawn_in_front_of_everything_else():
    view = shown(GO_NOTE, seconds=LAY_DELAY + 0.1)

    assert view.back_to_front()[-1].kind == "egg"


def texts(view: View, kind: str) -> list[str]:
    return [t.shape.text for t in view.things if t.kind == kind and isinstance(t.shape, Text)]


def test_a_hint_says_how_to_start_until_a_note_is_on_the_go_ring():
    assert (bool(texts(shown(), "hint")), texts(shown(GO_NOTE), "hint")) == (True, [])


def test_a_win_says_so_and_says_how_to_play_again():
    level = parse_level(
        {
            "format": 1,
            "name": "Won",
            "size": [1000, 600],
            "nest": {"at": [200, 100], "launch": [0, 0]},
            "blossom": {"at": [200, 400], "radius": 40},  # right under the nest
            "go": {"at": [900, 550], "radius": 40},
            "terrain": [],
        }
    )
    game = NestGame(level)
    scene = Scene(time=0.0, pieces=(note(99, level.go.at),))
    for _ in range(4 * 120):
        game.update(scene, 1 / 120)

    view = game.view()

    assert texts(view, "message") and "notes off" in texts(view, "hint")[0]
