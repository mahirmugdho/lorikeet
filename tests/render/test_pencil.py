"""The pencil style, shared by the desk and the sketch renderer: its wobble is an outline
traced by hand, close to the real one but never exact."""

import math
import random

from lorikeet.interface import Point, Polygon, square
from lorikeet.render.pencil import boil_frame, jittered

NOTE = square((100, 100), 100)


def distance_to_outline(point: Point, polygon: Polygon) -> float:
    def to_segment(a: Point, b: Point) -> float:
        (px, py), (ax, ay), (bx, by) = point, a, b
        t = ((px - ax) * (bx - ax) + (py - ay) * (by - ay)) / ((bx - ax) ** 2 + (by - ay) ** 2)
        t = min(1.0, max(0.0, t))
        return math.hypot(px - (ax + t * (bx - ax)), py - (ay + t * (by - ay)))

    return min(to_segment(a, b) for a, b in zip(polygon, polygon[1:] + polygon[:1], strict=True))


def test_every_edge_is_cut_into_the_given_number_of_steps():
    assert len(jittered(NOTE, random.Random(1), amount=2, steps=3)) == 4 * 3


def test_the_wobble_stays_within_reach_of_the_real_outline():
    # Each point moves up to `amount` along x and along y, so at most amount * sqrt(2).
    traced = jittered(NOTE, random.Random(1), amount=2, steps=3)

    assert max(distance_to_outline(point, NOTE) for point in traced) <= 2 * math.sqrt(2)


def test_the_same_seed_traces_the_same_wobble():
    assert jittered(NOTE, random.Random(5), amount=2) == jittered(NOTE, random.Random(5), amount=2)


def test_the_boil_frame_counts_tenths_of_a_second():
    assert [boil_frame(t) for t in (0.0, 0.09, 0.1, 1.25)] == [0, 0, 1, 12]
