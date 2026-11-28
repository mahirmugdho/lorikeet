"""Built meshes are kept on disk under a fingerprint of the recipe and step."""

import numpy as np

from lorikeet.render.clay.cache import built, detail
from lorikeet.render.clay.figure import Figure, Piece
from lorikeet.render.clay.shapes import Ellipsoid


def ball(radius: float) -> Figure:
    return Figure(
        (Piece(Ellipsoid((0, 0, 0), (radius, radius, radius)), "c"),), {"c": (90, 90, 90)}
    )


def test_a_mesh_is_built_once_then_read_back(tmp_path):
    first = built(ball(4), 1.0, tmp_path)
    again = built(ball(4), 1.0, tmp_path)

    assert len(list(tmp_path.glob("*.npz"))) == 1
    assert np.array_equal(first.positions, again.positions)
    assert np.array_equal(first.part_weights, again.part_weights)


def test_a_different_recipe_or_step_is_built_afresh(tmp_path):
    built(ball(4), 1.0, tmp_path)
    built(ball(5), 1.0, tmp_path)
    built(ball(4), 0.5, tmp_path)

    assert len(list(tmp_path.glob("*.npz"))) == 3


def test_the_fingerprint_texture_is_made_once_then_read_back(tmp_path):
    first = detail(size=32, folder=tmp_path)
    again = detail(size=32, folder=tmp_path)

    assert len(list(tmp_path.glob("detail-*.npz"))) == 1
    assert np.array_equal(first.rgba(), again.rgba())
