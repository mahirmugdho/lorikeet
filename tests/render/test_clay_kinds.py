"""Nest's other things in clay: each recipe builds into one closed, sensibly sized mesh."""

import numpy as np
import pytest

from lorikeet.render.clay.figure import build
from lorikeet.render.clay.kinds import blossom, egg, go_ring, ledge, nest


def extent(mesh) -> np.ndarray:
    return np.ptp(mesh.positions, axis=0)


def test_a_ledge_keeps_its_outline_and_reaches_back_to_the_backdrop():
    box = ((-100.0, -30.0), (100.0, -30.0), (100.0, 30.0), (-100.0, 30.0))
    mesh = build(ledge(box, back=28.0), step=2.0)

    x, _, z = extent(mesh)
    assert x == pytest.approx(200, abs=3)
    assert z == pytest.approx(60, abs=3)
    assert mesh.positions[:, 1].max() == pytest.approx(28, abs=2)


def test_the_nest_is_a_bowl_on_the_bottom_of_its_circle_deeper_in_front_than_behind():
    """Lori sits in it: its front wall stands well in front of its middle, where she is,
    and its back is shallow, so it fits in front of the backdrop."""
    bowl = nest(40)
    _, y, z = build(bowl, step=1.5).positions.T

    assert z.min() == pytest.approx(-40, abs=3)  # on the ground
    assert -y.min() > 1.5 * y.max()
    assert -y.min() > 30
    where_she_sits = np.array([(0, -10, -10), (0, -20, 0), (15, -15, -15), (-15, -5, -20)])
    assert (bowl.distance(where_she_sits.astype(np.float32)) > 0).all()  # no clay there


def test_the_egg_is_about_as_big_as_its_circle():
    mesh = build(egg(28), step=1.0)
    x, _, z = extent(mesh)
    assert x == pytest.approx(56, abs=3)
    assert z == pytest.approx(56, abs=4)


def test_the_blossom_and_the_go_ring_fill_their_circles():
    flower = build(blossom(45), step=1.0)
    ring = build(go_ring(70), step=1.5)
    assert extent(flower)[0] == pytest.approx(90, abs=10)
    assert extent(ring)[0] == pytest.approx(140, abs=3)
    centre = np.hypot(ring.positions[:, 0], ring.positions[:, 2]) < 50
    assert not centre.any()  # the go ring is empty in the middle
