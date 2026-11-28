"""How Nest plays: notes are ground, a note on the go spot lays eggs one at a time, and each
egg wins, breaks on the floor, falls off a side, or stalls. Small made-up levels keep each
rule's test independent of how the real levels are tuned."""

import copy
import math
from typing import Any

import pytest

from lorikeet.games.nest.game import BREAK_SECONDS, LAY_DELAY, NestGame, Outcome, State
from lorikeet.games.nest.level import Level, level_ids, load_level, parse_level
from lorikeet.interface import Piece, PieceState, Point, Scene

# A canvas with the nest high on the left, and nothing under it: eggs drop to the floor.
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
    piece_id: int,
    center: Point,
    angle: float = 0.0,
    state: PieceState = PieceState.SETTLED,
    color: str = "yellow",
) -> Piece:
    """A 100 px note, turned `angle` degrees clockwise on screen."""
    x, y = center
    cos, sin = math.cos(math.radians(angle)), math.sin(math.radians(angle))
    corners = ((-50, -50), (50, -50), (50, 50), (-50, 50))
    outline = tuple((x + dx * cos - dy * sin, y + dx * sin + dy * cos) for dx, dy in corners)
    return Piece(id=piece_id, color=color, state=state, outline=outline, parts=(outline,))


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


def test_an_egg_that_drops_onto_the_floor_breaks():
    level = made_up()
    game = NestGame(level)

    run_until_outcome(game, Scene(time=0.0, pieces=(go_note(level),)))

    assert game.outcomes == [Outcome.BROKEN]


def eggs(game: NestGame) -> list:
    return [thing for thing in game.view().things if thing.kind == "egg"]


def test_a_broken_egg_lies_cracked_on_the_floor_for_a_moment_then_the_next_egg_comes():
    level = made_up()
    game = NestGame(level)
    scene = Scene(time=0.0, pieces=(go_note(level),))
    run(game, scene, seconds=LAY_DELAY + 0.1)
    (flying,) = eggs(game)

    run_until_outcome(game, scene)
    (broken,) = eggs(game)
    assert broken.id == flying.id  # the same egg, now broken
    assert broken.pose == "broken"
    assert broken.position[1] == pytest.approx(600 - broken.shape.radius, abs=2)  # on the floor
    assert game.state is State.BROKEN
    assert game.egg is None  # nothing's in play while it lies there

    run(game, scene, seconds=BREAK_SECONDS - 0.1)
    assert eggs(game) == [broken]  # it stays where it broke
    run(game, scene, seconds=0.2)
    assert eggs(game) == []  # then it's gone...
    run(game, scene, seconds=LAY_DELAY)
    (next_egg,) = eggs(game)  # ...and Lori lays the next one
    assert next_egg.id != broken.id and next_egg.pose != "broken"


def test_an_egg_that_goes_off_a_side_is_lost():
    level = made_up(nest={"at": [200, 100], "launch": [-700, -100]})  # thrown off the left
    game = NestGame(level)

    run_until_outcome(game, Scene(time=0.0, pieces=(go_note(level),)))

    assert game.outcomes == [Outcome.FELL]


def test_eggs_keep_coming_one_at_a_time_while_the_go_note_stays():
    level = made_up()
    game = NestGame(level)

    run(game, Scene(time=0.0, pieces=(go_note(level),)), seconds=8)

    assert len(game.outcomes) >= 3
    assert set(game.outcomes) == {Outcome.BROKEN}


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

    assert game.outcomes == [Outcome.BROKEN]  # straight through to the floor


def test_the_note_on_the_go_spot_is_not_ground():
    level = made_up(go={"at": [200, 300], "radius": 40})  # the go spot is under the nest
    game = NestGame(level)

    run_until_outcome(game, Scene(time=0.0, pieces=(go_note(level),)))

    assert game.outcomes == [Outcome.BROKEN]  # straight through to the floor


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
    notes = tuple(
        note(i, n.at, n.angle, color=n.color) for i, n in enumerate(level.solution, start=1)
    )
    game = NestGame(level)

    run(game, Scene(time=0.0, pieces=(go_note(level), *notes)), seconds=20)

    assert game.state is State.WON, game.outcomes


@pytest.mark.parametrize("level_id", level_ids())
def test_no_level_is_won_by_the_go_note_alone(level_id: str):
    level = load_level(level_id)
    game = NestGame(level)

    run(game, Scene(time=0.0, pieces=(go_note(level),)), seconds=20)

    assert game.state is not State.WON


def win(game: NestGame, scene: Scene) -> None:
    for _ in range(10 * 60):
        if game.state is State.WON:
            return
        game.update(scene, 1 / 60)
    raise AssertionError(f"never won: {game.outcomes}")


GOAL_UNDER_NEST = {"blossom": {"at": [200, 400], "radius": 40}}


def test_clearing_the_wall_after_a_win_plays_the_level_again():
    level = made_up(**GOAL_UNDER_NEST)
    game = NestGame(level)
    win(game, Scene(time=0.0, pieces=(go_note(level),)))

    game.update(Scene(time=0.0), 1 / 60)

    assert (game.state, game.outcomes, game.level) == (State.WAITING, [], level)


def test_with_more_levels_clearing_the_wall_after_a_win_moves_to_the_next():
    first, second = made_up(**GOAL_UNDER_NEST), made_up(name="Second", **GOAL_UNDER_NEST)
    game = NestGame(first, second)
    win(game, Scene(time=0.0, pieces=(go_note(first),)))

    game.update(Scene(time=0.0), 1 / 60)

    assert game.level is second


def test_after_the_last_level_it_goes_back_to_the_first():
    first, second = made_up(**GOAL_UNDER_NEST), made_up(name="Second", **GOAL_UNDER_NEST)
    game = NestGame(first, second)
    for _ in range(2):
        win(game, Scene(time=0.0, pieces=(go_note(game.level),)))
        game.update(Scene(time=0.0), 1 / 60)

    assert game.level is first


def test_clearing_the_wall_before_a_win_changes_nothing():
    level = made_up()
    game = NestGame(level)
    run_until_outcome(game, Scene(time=0.0, pieces=(go_note(level),)))

    game.update(Scene(time=0.0), 1 / 60)

    assert game.outcomes == [Outcome.BROKEN]


def drop_note_on_the_falling_egg(game: NestGame, go: Piece) -> Piece:
    """Let an egg out, then stick a note over it, a little to one side so that pushing the
    egg out the short way would shove it sideways."""
    run(game, Scene(time=0.0, pieces=(go,)), seconds=LAY_DELAY + 0.3)
    assert game.egg is not None
    x, y = game.egg
    return note(1, (x + 20, y))


def test_a_note_stuck_on_top_of_the_egg_does_not_shove_it():
    level = made_up()  # nothing under the nest: the egg falls straight down at x=200
    game = NestGame(level)
    go = go_note(level)
    on_egg = drop_note_on_the_falling_egg(game, go)

    xs = []
    for _ in range(60):
        game.update(Scene(time=0.0, pieces=(go, on_egg)), 1 / 60)
        if game.egg is not None:
            xs.append(game.egg[0])

    assert max(abs(x - 200) for x in xs) < 2  # still falling straight down


def test_that_note_becomes_ground_once_the_egg_is_clear_of_it():
    level = made_up()
    game = NestGame(level)
    go = go_note(level)
    on_egg = drop_note_on_the_falling_egg(game, go)
    scene = Scene(time=0.0, pieces=(go, on_egg))
    run_until_outcome(game, scene)  # the first egg falls through and off the canvas

    run(game, scene, seconds=LAY_DELAY + 2)  # the next egg drops onto the note

    assert game.egg is not None and game.egg[1] < on_egg.center[1]  # resting on top of it


# What each colour does. In the pit, the egg falls straight down from (200, 100); a note
# under it at (200, 300) spans 250..350.
UNDER_NEST = (200, 300)


def egg_heights(level: Level, *notes: Piece, seconds: float) -> list[float]:
    """The egg's height (y) at each step, from when it's laid."""
    game = NestGame(level)
    scene = Scene(time=0.0, pieces=(go_note(level), *notes))
    run(game, scene, seconds=LAY_DELAY, dt=1 / 120)
    heights = []
    for _ in range(round(seconds * 120)):
        game.update(scene, 1 / 120)
        if game.egg is not None:
            heights.append(game.egg[1])
    return heights


def rebound_top(heights: list[float]) -> float:
    """How high the egg gets after it first hits the note (smaller y is higher)."""
    impact = heights.index(max(heights[:120]))
    return min(heights[impact:])


def test_a_pink_note_bounces_the_egg_higher_than_a_yellow_one():
    level = made_up()
    yellow = egg_heights(level, note(1, UNDER_NEST), seconds=2)
    pink = egg_heights(level, note(1, UNDER_NEST, color="pink"), seconds=2)

    assert rebound_top(pink) < rebound_top(yellow) - 30


def test_a_green_note_lets_the_egg_through_and_speeds_it_up():
    level = made_up()
    plain = egg_heights(level, seconds=0.7)
    green = egg_heights(level, note(1, UNDER_NEST, color="green"), seconds=0.7)

    assert green[-1] > plain[-1] + 20  # through the note, and further down than with none


def test_a_blue_note_lets_the_egg_in_and_slows_it_right_down():
    level = made_up()
    plain = egg_heights(level, seconds=0.7)
    blue = egg_heights(level, note(1, UNDER_NEST, color="blue"), seconds=0.7)

    # In the note (not resting on its top at 222), and far behind a free fall.
    assert 250 < blue[-1] < 380 < plain[-1]


def test_a_note_of_a_colour_without_a_meaning_is_solid():
    level = made_up()

    heights = egg_heights(level, note(1, UNDER_NEST, color="orange"), seconds=2)

    assert heights[-1] < 250  # resting on top of it
