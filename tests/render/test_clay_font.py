"""The clay font: every letter Nest writes is in it, laid out left to right, and each builds
into a clay letter the right size."""

import itertools

import numpy as np
import pytest

from lorikeet.render.clay.clayfont import CAP, DESCENT, LETTERS, ROPE, X_HEIGHT, glyph, layout
from lorikeet.render.clay.figure import build

NEST_WORDS = (
    "Stick a note on the go ring to start",
    "Lori's egg made it!",
    "Take the notes off to play again",
    "Take the notes off for the next level",
    "Loading…",
)


def test_every_letter_nest_writes_is_in_the_font():
    for words in NEST_WORDS:
        assert set(words) - {" "} <= set(LETTERS)


def test_letters_are_laid_out_left_to_right_without_touching():
    placed, length = layout("Lori's egg")
    starts = [x for _, x in placed]
    assert starts == sorted(starts)
    for (char, x), (_, after) in itertools.pairwise(placed):
        assert x + LETTERS[char][0] < after  # a gap after every letter
    assert length == pytest.approx(starts[-1] + LETTERS[placed[-1][0]][0])


def test_spaces_take_room_but_have_no_letter():
    with_space, wide = layout("a b")
    _without, narrow = layout("ab")
    assert [c for c, _ in with_space] == ["a", "b"]
    assert wide > narrow


def test_a_letter_builds_to_its_size_between_its_descender_and_cap_height():
    rope = ROPE * X_HEIGHT
    for char in "gT!o":
        z = build(glyph(char), step=1.0).positions[:, 2]
        assert z.min() >= DESCENT * X_HEIGHT - rope - 1.5
        assert z.max() <= CAP * X_HEIGHT + 2 * rope
    tall, short = (np.ptp(build(glyph(c), step=1.0).positions[:, 2]) for c in "lo")
    assert tall > 1.3 * short  # an l is taller than an o


def test_a_letter_the_font_lacks_is_written_as_a_question_mark():
    placed, _ = layout("a€")
    assert [c for c, _ in placed] == ["a", "?"]
