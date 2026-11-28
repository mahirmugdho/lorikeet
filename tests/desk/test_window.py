"""The desk's own window: the same game in pencil, with the desk's notes and palette, scaled
to fit. Headless here."""

from collections.abc import Iterator

import pygame
import pytest

from lorikeet.desk.window import DeskWindow
from lorikeet.render.sketch import PAPER
from lorikeet.view import View

CANVAS = (320, 180)


@pytest.fixture
def desk(monkeypatch: pytest.MonkeyPatch) -> Iterator[DeskWindow]:
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")  # CI has no display
    pygame.init()
    window = DeskWindow(CANVAS, scale=0.5)  # a 160x90 window showing a 320x180 canvas
    yield window
    window.close()
    pygame.quit()


def bare_wall() -> pygame.Surface:
    wall = pygame.Surface(CANVAS)
    wall.fill((255, 255, 255))
    return wall


def test_its_canvas_is_the_game_windows_size(desk: DeskWindow):
    assert desk.size == CANVAS


def draw(desk: DeskWindow) -> None:
    desk.draw(View(), bare_wall(), pygame.Surface(CANVAS, pygame.SRCALPHA))


def shown(desk: DeskWindow) -> tuple[int, ...]:
    return tuple(pygame.transform.average_color(desk.window.get_surface())[:3])


def test_it_draws_on_paper(desk: DeskWindow):
    draw(desk)
    draw(desk)

    assert shown(desk) == PAPER


def test_it_draws_one_frame_and_shows_it_the_next(desk: DeskWindow):
    # Split over two frames, so neither is heavy enough to slow the game window down.
    draw(desk)
    assert shown(desk) != PAPER  # drawn, not shown yet

    draw(desk)
    assert shown(desk) == PAPER


def test_mouse_positions_are_turned_into_canvas_pixels(desk: DeskWindow):
    click = pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(100, 50), button=1, window=desk.window)

    (mine,) = desk.events([click])

    assert mine.pos == pytest.approx((200, 100))  # the window shows the canvas at half size


def test_it_takes_no_input_from_other_windows(desk: DeskWindow):
    elsewhere = pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(100, 50), button=1, window=None)

    assert desk.events([elsewhere]) == []
