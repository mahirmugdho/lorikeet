"""The clay set is held out of sight until it has loaded, then shown all at once."""

from lorikeet.render.clay.loading import LIMIT, QUIET, Loading


def test_the_set_is_held_until_nothing_is_missing_then_shown_for_good():
    loading = Loading(started=0.0)

    assert loading.step(missing=5, now=0.0)[0]
    assert loading.step(missing=2, now=0.1)[0]
    assert loading.step(missing=0, now=0.2) == (False, False)
    assert loading.step(missing=3, now=5.0) == (False, False)  # a new thing later: no hold


def test_the_word_only_shows_if_loading_takes_long_enough_to_notice():
    loading = Loading(started=0.0)

    assert loading.step(missing=4, now=QUIET / 2) == (True, False)
    assert loading.step(missing=4, now=QUIET + 0.01) == (True, True)


def test_the_set_is_shown_anyway_if_loading_never_finishes():
    loading = Loading(started=0.0)

    assert loading.step(missing=1, now=LIMIT) == (False, False)
