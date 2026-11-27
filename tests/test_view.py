"""The View: what a game shows each frame, for whichever renderer is drawing (ADR 0008)."""

import math

import pytest

from lorikeet.view import Circle, Outline, Thing, View

SQUARE = Outline(((-5, -5), (5, -5), (5, 5), (-5, 5)))  # 10 px, around its own origin


def test_an_outline_is_placed_at_the_things_position():
    assert SQUARE.placed((100, 50), angle=0.0) == ((95, 45), (105, 45), (105, 55), (95, 55))


def test_a_positive_angle_turns_an_outline_clockwise_on_screen():
    # y grows downward, so a quarter turn clockwise takes the top-left corner to the top right.
    top_left = SQUARE.placed((100, 50), angle=math.pi / 2)[0]

    assert top_left == pytest.approx((105, 45))


def test_an_outline_needs_at_least_three_points():
    with pytest.raises(ValueError, match="3 points"):
        Outline(((0, 0), (10, 0)))


def test_a_circle_needs_a_positive_radius():
    with pytest.raises(ValueError, match="radius"):
        Circle(0)


def test_a_thing_starts_unturned_on_layer_zero_with_no_pose():
    thing = Thing(id=1, kind="egg", shape=Circle(6), position=(10, 20))

    assert (thing.angle, thing.layer, thing.pose) == (0.0, 0, "")


def test_ids_must_be_unique_in_a_view():
    egg = Thing(id=1, kind="egg", shape=Circle(6), position=(10, 20))

    with pytest.raises(ValueError, match="repeated: \\[1\\]"):
        View(things=(egg, egg))


def test_back_to_front_orders_by_layer_and_keeps_order_within_a_layer():
    def thing(i: int, layer: int) -> Thing:
        return Thing(id=i, kind="terrain", shape=Circle(1), layer=layer)

    view = View(things=(thing(1, 2), thing(2, 0), thing(3, 2), thing(4, 1)))

    assert [t.id for t in view.back_to_front()] == [2, 4, 1, 3]
