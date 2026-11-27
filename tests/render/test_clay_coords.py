"""Projector pixels and Panda3D's world: one mapping, checked both ways."""

import math

import pytest
from panda3d.core import NodePath, OrthographicLens, Point2, Point3

from lorikeet.render.clay.coords import heading, to_projector, to_world
from lorikeet.render.clay.stage import canvas_camera


def test_projector_pixels_round_trip_through_the_world():
    for point in [(0.0, 0.0), (1920.0, 1080.0), (123.5, 456.25), (-10.0, 2000.0)]:
        for depth in (0.0, 35.0, -12.0):
            assert to_projector(to_world(point, depth)) == point


def test_down_the_screen_is_down_the_world_and_depth_is_y():
    assert to_world((10, 20), depth=5) == (10, 5, -20)


def test_the_camera_shows_the_canvas_pixel_for_pixel():
    """Canvas corners land on the film's corners, whatever their depth."""
    lens, place = canvas_camera((1920, 1080))
    assert isinstance(lens, OrthographicLens)
    camera = NodePath("camera")
    camera.setPos(place)

    def film(point, depth) -> tuple[float, float]:
        seen = camera.getRelativePoint(NodePath(), Point3(*to_world(point, depth)))
        out = Point2()
        assert lens.project(seen, out)
        return out.x, out.y

    assert film((0, 0), 0) == pytest.approx((-1, 1))
    assert film((1920, 1080), 40) == pytest.approx((1, -1))
    assert film((960, 540), -20) == pytest.approx((0, 0))


def test_a_clockwise_game_angle_is_a_clockwise_roll_seen_from_the_camera():
    """Turn a point to the right of a thing by a quarter turn clockwise: on screen (y down)
    it ends up below the thing."""
    thing = NodePath("thing")
    thing.setR(heading(math.pi / 2))
    right = NodePath().getRelativePoint(thing, Point3(*to_world((10, 0))))
    assert to_projector((right.x, right.y, right.z)) == pytest.approx((0, 10), abs=1e-4)
