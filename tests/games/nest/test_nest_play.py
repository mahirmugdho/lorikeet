"""How Nest plays: notes are ground, a note on the go spot lays eggs one at a time, and each
egg wins, falls or stalls. Small made-up levels keep each rule's test independent of how the
real levels are tuned."""

import copy
import math
from typing import Any

import pytest

from lorikeet.games.nest.game import LAY_DELAY, NestGame, Outcome, State
from lorikeet.games.nest.level import Level, level_ids, load_level, parse_level
from lorikeet.interface import Piece, PieceState, Point, Scene

# A canvas with the nest high on the left, and nothing under it: eggs fall off the bottom.
PIT: dict[str, Any] = {
    "format": 1,
    "name": "Pit",
    "size": [1000, 600],
    "nest": {"at": [200, 100], "launch": [0, 0]},
    "blossom": {"at": [900, 100], "radius": 40},
    "go": {"at": [900, 550], "radius": 40},
    "terrain": [],
    "timeout_s": 3,
}


def made_up(**changes: Any) -> Level:
    data = copy.deepcopy(PIT)
    data.update(changes)
    return parse_level(data)


def note(
    piece_id: int, center: Point, angle: float = 0.0, state: PieceState = PieceState.SETTLED
) -> Piece:
    """A 100 px note, turned `angle` degrees clockwise on screen."""
    x, y = center
    cos, sin = math.cos(math.radians(angle)), math.sin(math.radians(angle))
    corners = ((-50, -50), (50, -50), (50, 50), (-50, 50))
    outline = tuple((x + dx * cos - dy * sin, y + dx * sin + dy * cos) for dx, dy in corners)
    return Piece(id=piece_id, color="yellow", state=state, outline=outline, parts=(outline,))


def go_note(level: Level, state: PieceState = PieceState.SETTLED) -> Piece:
    return note(999, level.go.at, state=state)


def run(game: NestGame, scene: Scene, seconds: float, dt: float = 1 / 60) -> None:
    for _ in range(round(seconds / dt)):
        game.update(scene, dt)


def run_until_outcome(game: NestGame, scene: Scene, limit: float = 20) -> None:
    for _ in range(round(limit * 60)):
        if game.outcomes:
            return
        game.update(scene, 1 / 60)


def test_nothing_happens_without_a_note_on_the_go_spot():
    game = NestGame(made_up())

    run(game, Scene(time=0.0), seconds=3)

    assert (game.state, game.egg, game.outcomes) == (State.WAITING, None, [])


def test_a_note_on_the_go_spot_lays_an_egg_at_the_nest():
    level = made_up()
    game = NestGame(level)

    run(game, Scene(time=0.0, pieces=(go_note(level),)), seconds=LAY_DELAY + 1 / 60)

    assert game.egg == pytest.approx(level.nest.at, abs=5)


def test_a_note_still_in_a_hand_does_not_start_the_eggs():
    level = made_up()
    game = NestGame(level)

    run(game, Scene(time=0.0, pieces=(go_note(level, PieceState.MOVING),)), seconds=3)

    assert game.egg is None


def test_an_egg_that_falls_off_the_canvas_is_lost():
    level = made_up()
    game = NestGame(level)

    run_until_outcome(game, Scene(time=0.0, pieces=(go_note(level),)))

    assert game.outcomes == [Outcome.FELL]


def test_eggs_keep_coming_one_at_a_time_while_the_go_note_stays():
    level = made_up()
    game = NestGame(level)

    run(game, Scene(time=0.0, pieces=(go_note(level),)), seconds=8)

    assert len(game.outcomes) >= 3
    assert set(game.outcomes) == {Outcome.FELL}


def test_taking_the_go_note_off_stops_new_eggs():
    level = made_up()
    game = NestGame(level)
    run_until_outcome(game, Scene(time=0.0, pieces=(go_note(level),)))

    run(game, Scene(time=0.0), seconds=5)

    assert (len(game.outcomes), game.egg) == (1, None)


def test_an_egg_that_reaches_the_blossom_wins_and_no_more_are_laid():
    level = made_up(blossom={"at": [200, 400], "radius": 40})  # right under the nest
    game = NestGame(level)

    run(game, Scene(time=0.0, pieces=(go_note(level),)), seconds=6)

    assert (game.state, game.outcomes) == (State.WON, [Outcome.WON])


def test_an_egg_that_stops_getting_closer_to_the_blossom_stalls():
    level = made_up(terrain=[{"box": [0, 300, 600, 40]}])  # a floor under the nest
    game = NestGame(level)

    run_until_outcome(game, Scene(time=0.0, pieces=(go_note(level),)))

    assert game.outcomes == [Outcome.STALLED]


def test_a_stuck_down_note_is_ground():
    level = made_up()
    game = NestGame(level)
    catcher = note(1, (200, 300))  # under the nest
    scene = Scene(time=0.0, pieces=(go_note(level), catcher))

    run(game, scene, seconds=LAY_DELAY + 2)

    assert game.egg is not None and game.egg[1] < 250  # resting on top of the note


def test_a_note_still_in_a_hand_is_not_ground():
    level = made_up()
    game = NestGame(level)
    held = note(1, (200, 300), state=PieceState.MOVING)

    run_until_outcome(game, Scene(time=0.0, pieces=(go_note(level), held)))

    assert game.outcomes == [Outcome.FELL]


def test_the_note_on_the_go_spot_is_not_ground():
    level = made_up(go={"at": [200, 300], "radius": 40})  # the go spot is under the nest
    game = NestGame(level)

    run_until_outcome(game, Scene(time=0.0, pieces=(go_note(level),)))

    assert game.outcomes == [Outcome.FELL]


def test_the_same_notes_always_play_out_the_same_way():
    level = made_up(terrain=[{"polygon": [[100, 300], [400, 360], [400, 380], [100, 320]]}])
    scene = Scene(time=0.0, pieces=(go_note(level),))
    first, second = NestGame(level), NestGame(level)

    run(first, scene, seconds=2)
    run(second, scene, seconds=2)

    assert first.egg == second.egg


def test_the_game_runs_at_the_same_speed_at_any_frame_rate():
    level = made_up(terrain=[{"polygon": [[100, 300], [400, 360], [400, 380], [100, 320]]}])
    scene = Scene(time=0.0, pieces=(go_note(level),))
    at_60, at_144 = NestGame(level), NestGame(level)

    run(at_60, scene, seconds=2, dt=1 / 60)
    run(at_144, scene, seconds=2, dt=1 / 144)

    assert at_60.egg == pytest.approx(at_144.egg)


@pytest.mark.parametrize("level_id", level_ids())
def test_each_levels_stored_solution_wins(level_id: str):
    level = load_level(level_id)
    notes = tuple(note(i, n.at, n.angle) for i, n in enumerate(level.solution, start=1))
    game = NestGame(level)

    run(game, Scene(time=0.0, pieces=(go_note(level), *notes)), seconds=20)

    assert game.state is State.WON, game.outcomes


@pytest.mark.parametrize("level_id", level_ids())
def test_no_level_is_won_by_the_go_note_alone(level_id: str):
    level = load_level(level_id)
    game = NestGame(level)

    run(game, Scene(time=0.0, pieces=(go_note(level),)), seconds=20)

    assert game.state is not State.WON
