"""The fingerprint, smudge and crack texture tiles without a seam and stays subtle."""

import numpy as np
import pytest

from lorikeet.render.clay.detail import clay_detail


@pytest.fixture(scope="module")
def detail():
    return clay_detail(size=256, seed=3)


def test_the_texture_tiles_without_a_seam(detail):
    """Across the tile's edge, neighbouring texels differ no more than inside it."""
    slopes = detail.slopes[..., 0]
    inside = np.abs(np.diff(slopes, axis=1)).mean()
    across_edge = np.abs(slopes[:, 0] - slopes[:, -1]).mean()
    assert across_edge < 1.5 * inside
    down_inside = np.abs(np.diff(slopes, axis=0)).mean()
    down_edge = np.abs(slopes[0, :] - slopes[-1, :]).mean()
    assert down_edge < 1.5 * down_inside


def test_the_texture_tilts_the_surface_gently(detail):
    """Subtle, as clay is: most slopes are small, so it never reads as orange peel."""
    tilt = np.degrees(np.arctan(np.linalg.norm(detail.slopes, axis=2)))
    assert np.median(tilt) < 12
    assert np.isfinite(detail.rgba()).all()


def test_there_are_a_few_cracks_not_a_web(detail):
    cracked = (detail.cavity > 0.3).mean()
    assert 0 < cracked < 0.01


def test_the_same_seed_gives_the_same_clay():
    a, b = clay_detail(size=64, seed=1), clay_detail(size=64, seed=1)
    assert np.array_equal(a.rgba(), b.rgba())
    assert a.rgba().shape == (64, 64, 4)
