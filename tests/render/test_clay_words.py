"""The View's words go up on cards where it says, and come down when they leave it."""

import pytest
from panda3d.core import NodePath

from lorikeet.render.clay.words import Words
from lorikeet.view import Circle, Text, Thing, View

CANVAS = (1920, 1080)


def test_words_are_centred_where_the_view_puts_them():
    root = NodePath("canvas 2d")
    words = Words(root, CANVAS)
    hint = Thing(6, "hint", Text("Stick a note on the go ring to start", 40), (960, 173))

    words.show(View((hint, Thing(1, "egg", Circle(28), (5, 5)))))

    (card,) = root.getChildren()  # one card, and nothing for the egg
    width, height = card.getPythonTag("size")
    left, top = (card.getX() + 1) / 2 * CANVAS[0], (1 - card.getZ()) / 2 * CANVAS[1]
    assert left + width / 2 == pytest.approx(960, abs=1)
    assert top + height / 2 == pytest.approx(173, abs=1)
    assert (left, top) == pytest.approx((round(left), round(top)), abs=1e-3)  # whole pixels


def test_words_that_leave_the_view_come_down_and_new_words_replace_old():
    root = NodePath("canvas 2d")
    words = Words(root, CANVAS)
    words.show(View((Thing(5, "message", Text("Lori's egg made it!", 76), (960, 173)),)))
    first = root.getChildren()[0]

    words.show(View((Thing(5, "message", Text("Again!", 76), (960, 173)),)))
    assert first.isEmpty() or first.getParent() != root  # the old words went
    assert root.getNumChildren() == 1

    words.show(View(()))
    assert root.getNumChildren() == 0
