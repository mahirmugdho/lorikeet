"""A window too big for the screen is shrunk to fit it, keeping the canvas's shape."""

import pytest

from lorikeet.render.flat import window_to_fit


def test_a_canvas_that_fits_the_screen_leaves_the_window_to_scaled():
    assert window_to_fit((320, 180), desktop=(1920, 1080)) is None


def test_a_canvas_wider_than_the_screen_gets_a_window_as_wide_as_fits():
    # A 1920x1080 canvas on a laptop's 1512x982-point desktop used to open past the screen's edge.
    fitted = window_to_fit((1920, 1080), desktop=(1512, 982))

    assert fitted is not None
    width, height = fitted
    assert width == round(1512 * 0.9)  # room left for the menu bar, dock or taskbar
    assert width / height == pytest.approx(1920 / 1080, rel=0.01)  # the canvas's shape


def test_a_canvas_taller_than_the_screen_gets_a_window_as_tall_as_fits():
    fitted = window_to_fit((1000, 2000), desktop=(1920, 1080))

    assert fitted is not None
    width, height = fitted
    assert height == round(1080 * 0.9)
    assert width / height == pytest.approx(1000 / 2000, rel=0.01)
