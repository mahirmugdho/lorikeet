"""The clay set is held out of sight until it has loaded, then shown all at once; the
loading screen's beads count the arrivals."""

from lorikeet.render.clay.loading import LIMIT, QUIET, Loading
from lorikeet.render.clay.loading_art import BEADS


def test_the_set_is_held_until_nothing_is_missing_then_shown_for_good():
    loading = Loading(started=0.0)

    assert loading.step(missing=5, now=0.0).holding
    assert loading.step(missing=2, now=0.1).holding
    assert not loading.step(missing=0, now=0.2).holding
    assert not loading.step(missing=3, now=5.0).holding  # a new thing later: no hold


def test_the_screen_only_shows_if_loading_takes_long_enough_to_notice():
    loading = Loading(started=0.0)

    assert not loading.step(missing=4, now=QUIET / 2).screen
    assert loading.step(missing=4, now=QUIET + 0.01).screen


def test_the_set_is_shown_anyway_if_loading_never_finishes():
    loading = Loading(started=0.0)

    assert not loading.step(missing=1, now=LIMIT).holding


def test_beads_fill_the_track_as_things_arrive_and_never_go_back():
    loading = Loading(started=0.0)
    beads = [loading.step(missing, now=2.0).beads for missing in (8, 8, 6, 7, 4, 2, 1)]

    assert beads[0] == 0
    assert beads == sorted(beads)  # never back, even when the count wobbles up
    assert 0 < beads[-1] < BEADS


def test_beads_can_follow_how_much_is_built_instead():
    loading = Loading(started=0.0)
    beads = [loading.step(3, now=2.0, built=share).beads for share in (0.0, 0.25, 0.5, 0.4, 0.9)]

    assert beads == [0, BEADS // 4, BEADS // 2, BEADS // 2, int(0.9 * BEADS)]
