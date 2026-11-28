"""A clay egg breaks open over a few stop-motion frames: the crack shows, the top half tips
over and lands beside the bottom half, and the puddle spreads."""

import numpy as np
import pytest

from lorikeet.render.clay.breaking import TIPS, _top_surface, puddle, top_half

R = 28.0


def lowest(m: np.ndarray) -> float:
    points = _top_surface(R)
    return float(np.min(points @ m[:3, :3].T[:, 2] + m[2, 3]))


def test_first_the_top_half_sits_on_the_bottom_half_so_the_crack_shows():
    assert np.allclose(top_half(R, 1), np.eye(4))
    assert puddle(1) == 0


def test_then_it_tips_over_further_each_frame_until_it_lies_on_its_side():
    tips = [
        -np.degrees(np.arctan2(top_half(R, k)[0, 2], top_half(R, k)[0, 0])) for k in range(1, 9)
    ]
    assert tips[1] < 0  # tipping right
    tipping = tips[:5]
    assert tipping == sorted(tipping, reverse=True)  # further each frame
    assert tips[-1] == pytest.approx(TIPS[-1], abs=0.1)  # then lies still


def test_it_never_goes_into_the_ground_and_ends_up_lying_on_it():
    for k in range(12):
        assert lowest(top_half(R, k)) >= -R - 0.01
    assert lowest(top_half(R, 10)) == pytest.approx(-R, abs=0.01)


def test_it_lands_to_the_right_of_the_bottom_half():
    assert top_half(R, 10)[0, 3] > 0.5 * R


def test_the_puddle_spreads_to_its_full_size():
    spreads = [puddle(k) for k in range(10)]
    assert spreads[0] == spreads[1] == 0
    assert spreads[-1] == 1.0
    assert max(spreads) > 1.0  # it spreads a touch past, and settles
