"""The clay window's plumbing: monitors, fitting the canvas, and keys as pygame keys."""

import pygame
import pytest

from lorikeet.render.clay.window import (
    Monitor,
    fit,
    letterbox,
    parse_monitors,
    pygame_key,
    pygame_settings,
)

LISTING = """Monitors: 2
 0: +*eDP-1 2880/285x1920/190+0+0  eDP-1
 1: +DP-1 2880/600x1620/340+2880+0  DP-1
"""


def test_monitors_are_read_from_xrandr_in_order():
    assert parse_monitors(LISTING) == [
        Monitor("eDP-1", 0, 0, 2880, 1920, primary=True),
        Monitor("DP-1", 2880, 0, 2880, 1620),
    ]


def test_no_monitors_in_an_empty_or_odd_listing():
    assert parse_monitors("") == []
    assert parse_monitors("Monitors: 0\n") == []


def test_a_canvas_that_fits_keeps_its_size_and_one_that_doesnt_shrinks_in_shape():
    assert fit((1920, 1080), (2880, 1920)) == (1920, 1080)
    width, height = fit((1920, 1080), (1512, 982))
    assert width <= 0.9 * 1512 and height <= 0.9 * 982
    assert width / height == pytest.approx(1920 / 1080, rel=0.01)


def test_the_canvas_fills_the_window_on_the_side_that_matches():
    assert letterbox((1920, 1080), (1920, 1080)) == (1.0, 1.0)
    assert letterbox((2880, 1620), (1920, 1080)) == pytest.approx((1.0, 1.0))
    sx, sz = letterbox((1920, 1200), (1920, 1080))  # a taller window: bars top and bottom
    assert sx == 1.0
    assert sz == pytest.approx(1080 / 1200)


def test_panda_keys_become_pygame_keys():
    pygame.init()
    assert pygame_key("escape") == pygame.K_ESCAPE
    assert pygame_key("d") == pygame.K_d
    assert pygame_key("arrow_left") == pygame.K_LEFT
    assert pygame_key("mouse1") is None


def test_beside_panda3d_pygame_draws_through_x11_on_linux_and_never_through_opengl():
    """Through Wayland, or through OpenGL, the desk window fails or flashes black once the
    clay window is open."""
    assert pygame_settings("linux") == {
        "SDL_VIDEODRIVER": "x11",
        "SDL_FRAMEBUFFER_ACCELERATION": "0",
    }
    assert pygame_settings("darwin") == {"SDL_FRAMEBUFFER_ACCELERATION": "0"}
