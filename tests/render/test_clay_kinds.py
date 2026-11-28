"""Nest's other things in clay: each recipe builds into one closed, sensibly sized mesh."""

import numpy as np
import pytest

from lorikeet.render.clay.figure import build
from lorikeet.render.clay.kinds import (
    GO_THICKNESS,
    bed_leaves,
    broken_egg,
    egg,
    flower_head,
    go_disc,
    ledge,
    nest,
)


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


def test_the_egg_is_egg_shaped_and_about_as_big_as_its_ball():
    mesh = build(egg(28), step=1.0)
    x, _, z = extent(mesh)
    assert z / x == pytest.approx(1.22, abs=0.08)  # taller than it's wide
    assert (x + z) / 2 == pytest.approx(56, abs=4)  # about the ball's size
    p = mesh.positions
    below = np.ptp(p[np.abs(p[:, 2] + 10) < 1.5][:, 0])
    above = np.ptp(p[np.abs(p[:, 2] - 14) < 1.5][:, 0])
    assert above < below  # narrower at the top


def test_the_go_disc_fills_its_circle_with_go_standing_out_on_it():
    mesh = build(go_disc(70), step=1.5)
    assert extent(mesh)[0] == pytest.approx(140, abs=3)
    assert extent(mesh)[2] == pytest.approx(140, abs=3)
    front = mesh.positions[:, 1].min()
    assert front < -GO_THICKNESS / 2 - 3  # the letters stand out in front of the face


def test_a_flower_opens_wider_stage_by_stage():
    widths = [extent(build(flower_head(22, stage), step=0.6))[0] for stage in range(4)]
    assert widths == sorted(widths)
    assert widths[-1] > 2 * widths[0]


def test_the_flower_beds_leaves_sit_on_the_ground_a_little_wider_than_its_circle():
    mesh = build(bed_leaves(45), step=1.5)
    assert extent(mesh)[0] == pytest.approx(2.6 * 45, rel=0.1)
    assert mesh.positions[:, 2].min() == pytest.approx(-45, abs=8)


def test_a_broken_egg_is_two_cracked_halves_resting_on_the_ground_in_a_puddle():
    mesh = build(broken_egg(28), step=0.8)
    x, z = mesh.positions[:, 0], mesh.positions[:, 2]

    assert z.min() == pytest.approx(-28, abs=3.5)  # everything rests on the ground
    assert z.max() < 28  # the top half isn't on top any more...
    assert x.max() > 50  # ...it's lying over to the right
