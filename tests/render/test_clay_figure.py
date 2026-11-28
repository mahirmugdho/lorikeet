"""Figures are pieces of coloured clay pressed together; Lori is one of them."""

import numpy as np
import pytest

from lorikeet.render.clay.colour import linear, srgb
from lorikeet.render.clay.figure import Figure, Piece, build, occlusion_at
from lorikeet.render.clay.lori import CLAYS, lori
from lorikeet.render.clay.shapes import Ellipsoid


def two_balls(**options) -> Figure:
    return Figure(
        (
            Piece(Ellipsoid((-4, 0, 0), (5, 5, 5)), "red"),
            Piece(Ellipsoid((4, 0, 0), (5, 5, 5)), "blue", blend=3),
        ),
        {"red": (200, 40, 40), "blue": (40, 40, 200)},
        **options,
    )


def test_colours_round_trip_through_linear_light():
    for colour in [(0, 0, 0), (255, 255, 255), (72, 84, 214), (128, 128, 128)]:
        assert srgb(linear(colour)) == colour
    assert linear((128, 128, 128))[0] == pytest.approx(0.216, abs=0.001)  # not 0.5


def nearest_colour(mesh) -> np.ndarray:
    """What the shader does: each point takes the colour of the clay it's nearest."""
    return mesh.palette[np.argmin(mesh.clay_distances, axis=1)]


def test_each_point_takes_the_colour_of_the_clay_it_is_nearest():
    mesh = build(two_balls(), step=0.5)

    left = mesh.positions[:, 0] < -0.5
    right = mesh.positions[:, 0] > 0.5
    assert np.allclose(nearest_colour(mesh)[left], linear((200, 40, 40)))
    assert np.allclose(nearest_colour(mesh)[right], linear((40, 40, 200)))
    assert np.allclose(mesh.tint, 1)


def test_the_line_between_two_clays_falls_where_they_are_equally_near():
    """The GPU blends the distances linearly across each triangle, so the colour changes
    where the blended gap between the two clays is zero: here, at x = 0."""
    mesh = build(two_balls(), step=0.5)

    gap = mesh.clay_distances[:, 0] - mesh.clay_distances[:, 1]
    a, b = (mesh.triangles[:, i] for i in range(2))
    crossing = np.sign(gap[a]) != np.sign(gap[b])
    t = gap[a][crossing] / (gap[a][crossing] - gap[b][crossing])
    x = mesh.positions[a][crossing, 0] * (1 - t) + mesh.positions[b][crossing, 0] * t
    assert len(x) > 20
    assert np.abs(x).max() < 0.05


def test_a_seam_is_a_shallow_groove_where_two_clays_meet():
    plain, seamed = two_balls(), two_balls(seam_depth=0.4, seam_width=0.5)
    on_join = np.array([[0.0, 0.0, 3.0]], dtype=np.float32)  # where the two balls meet
    away = np.array([[-9.0, 0.0, 0.0]], dtype=np.float32)  # the far side of the red ball

    assert seamed.distance(on_join)[0] == pytest.approx(plain.distance(on_join)[0] + 0.4)
    assert seamed.distance(away)[0] == pytest.approx(plain.distance(away)[0])


def test_lumps_move_the_surface_only_a_little():
    smooth, lumpy = two_balls(), two_balls(lump_height=0.3, lump_size=4)
    rng = np.random.default_rng(0)
    directions = rng.normal(size=(2000, 3))
    directions /= np.linalg.norm(directions, axis=1, keepdims=True)
    near_surface = (-4, 0, 0) + directions * rng.uniform(4, 6, (2000, 1))  # the left ball's
    p = near_surface.astype(np.float32)

    change = lumpy.distance(p) - smooth.distance(p)

    assert np.abs(change).max() <= 0.3 * (1 + 1 / 3) + 1e-6
    assert change.std() > 0.03  # but it does move


def test_occlusion_is_dark_in_the_crease_and_open_elsewhere():
    figure = two_balls()
    crease = np.array([[0.0, 0.0, 3.4]], dtype=np.float32)
    crease_normal = np.array([[0.0, 0.0, 1.0]], dtype=np.float32)
    outside = np.array([[-9.0, 0.0, 0.0]], dtype=np.float32)
    outside_normal = np.array([[-1.0, 0.0, 0.0]], dtype=np.float32)

    in_crease = occlusion_at(figure.distance, crease, crease_normal, reach=3)
    in_open = occlusion_at(figure.distance, outside, outside_normal, reach=3)

    assert in_open[0] > 0.95
    assert in_crease[0] < in_open[0] - 0.2


def test_a_piece_in_an_unknown_clay_is_refused():
    with pytest.raises(ValueError, match="no colour"):
        Figure((Piece(Ellipsoid((0, 0, 0), (1, 1, 1)), "mauve"),), {"red": (255, 0, 0)})


def test_lori_is_one_closed_figure_in_all_her_colours():
    mesh = build(lori(), step=0.8)

    height = mesh.positions[:, 2].max() - mesh.positions[:, 2].min()
    assert height == pytest.approx(68, rel=0.1)  # the game's Lori has radius 34
    colours = {tuple(np.round(c, 5)) for c in nearest_colour(mesh).tolist()}
    assert colours == {tuple(np.round(linear(c), 5)) for c in CLAYS.values()}
    assert 0 < mesh.occlusion.min() < 0.7 < mesh.occlusion.max() <= 1


def test_lori_scales_with_her_radius():
    small, big = build(lori(17), step=0.8), build(lori(34), step=0.8)

    def height(mesh) -> float:
        return float(np.ptp(mesh.positions[:, 2]))

    assert height(big) == pytest.approx(2 * height(small), rel=0.05)


def test_mottling_varies_the_clay_colour_faintly():
    """Real plasticine isn't one perfectly even colour: pigment and handling leave faint
    lighter and darker patches. The tint carries that, a few percent either way."""
    plain = build(two_balls(), step=0.5)
    mottled = build(two_balls(mottle=0.05, mottle_size=3), step=0.5)

    assert np.allclose(plain.tint, 1)
    assert mottled.tint.mean() == pytest.approx(1, abs=0.02)
    assert 0.01 < mottled.tint.std() < 0.05
    assert np.abs(mottled.tint - 1).max() < 0.15


def test_part_weights_are_whole_on_a_part_and_shared_at_the_join():
    figure = Figure(
        (
            Piece(Ellipsoid((-4, 0, 0), (5, 5, 5)), "red"),
            Piece(Ellipsoid((4, 0, 0), (5, 5, 5)), "red", blend=3, part="head"),
        ),
        {"red": (200, 40, 40)},
    )

    w = figure.part_weights(points_at((-9, 0, 0), (9, 0, 0), (0, 0, 3)))

    assert figure.part_names == ["", "head"]
    assert w.sum(axis=1) == pytest.approx([1, 1, 1])
    assert w[0, 0] > 0.97 and w[1, 1] > 0.97  # far ends: all body, all head
    assert w[2] == pytest.approx([0.5, 0.5], abs=0.01)  # the join: half and half


def points_at(*xyz) -> np.ndarray:
    return np.array(xyz, dtype=np.float32)
