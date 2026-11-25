"""Game-state rules that sit above the physics: the ghost of the last run."""

from lorikeet.games.puzzle.app import Game, Mode
from lorikeet.games.puzzle.level import load_level
from lorikeet.games.puzzle.sim import Outcome, PlacedNote


def play_out(game: Game) -> None:
    game.drop()
    while game.mode is Mode.PLAY:
        game.update()


def back_to_build(game: Game) -> None:
    for _ in range(10 * 120):
        if game.mode is Mode.BUILD:
            return
        game.update()
    game.set_mode(Mode.BUILD)  # a win waits for the player; step past it


def test_a_finished_run_leaves_a_ghost_path() -> None:
    level = load_level("1-1")
    game = Game(level)
    game.set_mode(Mode.BUILD)
    assert game.ghost is None
    play_out(game)  # no notes, so the egg splats on the floor
    ghost = game.ghost
    assert ghost is not None
    assert ghost.outcome is Outcome.SPLAT
    assert len(ghost.points) > 10
    assert abs(ghost.points[0][0] - level.nest[0]) < 3  # it starts at the nest...
    assert ghost.points[-1] == ghost.end  # ...and ends where the egg did


def test_the_ghost_lasts_into_the_next_run_until_that_one_ends() -> None:
    level = load_level("1-1")
    game = Game(level)
    game.set_mode(Mode.BUILD)
    play_out(game)
    first = game.ghost
    back_to_build(game)
    assert game.ghost is first  # still there to plan against

    game.placed = [PlacedNote(*n) for n in level.solution]
    game.drop()
    game.update()
    assert game.ghost is first  # the old path shows while the new run plays
    while game.mode is Mode.PLAY:
        game.update()
    assert game.ghost is not first
    assert game.ghost is not None
    assert game.ghost.outcome is Outcome.WON
    assert game.ghost.springs, "the Sun bounce should be marked on the path"
