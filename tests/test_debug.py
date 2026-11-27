"""The debug overlay shows what games are told: each piece's edge, styled by state, with its
id, colour and state. It stays out of the way until you press D."""

import pygame

from lorikeet.debug import DebugOverlay
from lorikeet.interface import FakeSceneSource, Piece, PieceState, Scene, square

NOTE = square((200, 150), 100)  # its left edge is at x=150
GAME = (90, 120, 150)  # stands in for whatever the game drew


def note(state: PieceState) -> Piece:
    return Piece(id=1, color="yellow", state=state, outline=NOTE, parts=(NOTE,))


def debug_over(*pieces: Piece, presses: int = 1) -> pygame.Surface:
    """The canvas after the debug overlay draws `pieces` over the game, with D pressed
    `presses` times first."""
    overlay = DebugOverlay(FakeSceneSource([Scene(time=0.0, pieces=pieces)]))
    for _ in range(presses):
        overlay.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_d))
    canvas = pygame.Surface((400, 300))
    canvas.fill(GAME)
    overlay.draw(canvas)
    return canvas


def changed_pixels(canvas: pygame.Surface) -> int:
    return sum(
        canvas.get_at((x, y))[:3] != GAME
        for x in range(canvas.get_width())
        for y in range(canvas.get_height())
    )


def test_it_draws_nothing_until_you_press_d():
    assert changed_pixels(debug_over(note(PieceState.SETTLED), presses=0)) == 0


def test_pressing_d_again_hides_it():
    assert changed_pixels(debug_over(note(PieceState.SETTLED), presses=2)) == 0


def test_a_piece_has_its_edge_drawn():
    assert debug_over(note(PieceState.SETTLED)).get_at((150, 150))[:3] != GAME


def test_the_inside_of_a_piece_is_left_alone():
    # On the projector, light inside the outline would land on the real note and shift
    # its colour for the camera (ADR 0006).
    assert debug_over(note(PieceState.SETTLED)).get_at((200, 150))[:3] == GAME


def test_a_settled_piece_has_a_heavier_edge_than_a_moving_one():
    assert changed_pixels(debug_over(note(PieceState.SETTLED))) > changed_pixels(
        debug_over(note(PieceState.MOVING))
    )
