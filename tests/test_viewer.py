"""The viewer draws what games are told: each piece's edge, styled by state, and nothing inside."""

import pygame

from lorikeet.interface import Piece, PieceState, Scene, square
from lorikeet.viewer import BACKGROUND, Viewer

NOTE = square((200, 150), 100)  # its left edge is at x=150


def drawn(*pieces: Piece) -> pygame.Surface:
    canvas = pygame.Surface((400, 300))
    viewer = Viewer()
    viewer.update(Scene(time=0.0, pieces=pieces), dt=0.0)
    viewer.draw(canvas)
    return canvas


def note(state: PieceState) -> Piece:
    return Piece(id=1, color="yellow", state=state, outline=NOTE, parts=(NOTE,))


def lit_pixels(canvas: pygame.Surface) -> int:
    return sum(
        canvas.get_at((x, y))[:3] != BACKGROUND
        for x in range(canvas.get_width())
        for y in range(canvas.get_height())
    )


def test_an_empty_scene_is_all_background():
    assert lit_pixels(drawn()) == 0


def test_a_piece_has_its_edge_drawn():
    assert drawn(note(PieceState.SETTLED)).get_at((150, 150))[:3] != BACKGROUND


def test_the_inside_of_a_piece_stays_dark():
    # On the projector, light inside the outline would land on the real note and shift
    # its colour for the camera (ADR 0006).
    assert drawn(note(PieceState.SETTLED)).get_at((200, 150))[:3] == BACKGROUND


def test_a_settled_piece_has_a_heavier_edge_than_a_moving_one():
    assert lit_pixels(drawn(note(PieceState.SETTLED))) > lit_pixels(drawn(note(PieceState.MOVING)))
