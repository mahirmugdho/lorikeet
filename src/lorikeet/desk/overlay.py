"""The desk's overlay: what the desk draws on top of the game's frame, and its mouse input.

With real notes, the paper is on the wall and the projector shines on it. At the desk there
is no paper, so the overlay draws each note over the game's frame, sketched in pencil with
line boil and a soft shadow (see `sketch`). Then it draws the palette and, on top, the note
in your hand, lifted higher so its shadow is bigger and softer. The launcher draws the
overlay after the game, and the game never knows it's there.
"""

from __future__ import annotations

import math
import random
import time
from collections.abc import Callable

import pygame

from lorikeet.desk.mouse import DeskMouse
from lorikeet.desk.source import DeskSceneSource
from lorikeet.interface import PieceState, Point, Polygon, square
from lorikeet.render.pencil import (
    PENCIL,
    Shadows,
    boil_frame,
    jittered,
    pencil_loop,
    pencil_outline,
    seeded,
)

PAPER = {
    "yellow": (250, 222, 90),
    "pink": (245, 135, 180),
    "green": (135, 215, 125),
    "blue": (110, 180, 240),
    "orange": (250, 165, 75),
    "purple": (185, 145, 230),
    "red": (235, 95, 90),
}
"""How each colour name looks on screen. This is only for drawing the desk's notes:
detection keeps its own thresholds for each name, calibrated per room."""

UNKNOWN_PAPER = (170, 170, 170)
"""For a colour name the table above doesn't know."""

TRAY = (214, 208, 196)
"""The palette's tray: card, a little darker than the backdrop."""

HINT = "Drag a note from the pad onto the desk"

_RESTING = ((3, 5), 4, 70)
"""Shadow offset, blur and darkness for something lying on the desk."""
_LIFTED = ((12, 18), 9, 55)
"""The same for the note in your hand: further off and softer, because it's higher up."""
_HELD_ALPHA = 200  # the held note is a little see-through, to show where it will land

# Boil seeds for the shapes that aren't pieces, kept clear of piece ids (which count up from 1).
_HELD, _TRAY, _HINT, _SWATCH, _CIRCLE = -1, -2, -3, -100, -200


class DeskOverlay:
    def __init__(
        self,
        source: DeskSceneSource,
        mouse: DeskMouse,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._source = source
        self._mouse = mouse
        self._clock = clock  # drives the boil; tests pass a fake one
        self._shadows = Shadows()
        pygame.font.init()
        self._font = pygame.font.Font(None, 40)

    def handle(self, event: pygame.event.Event) -> None:
        if event.type == pygame.MOUSEBUTTONDOWN:
            self._mouse.press(event.pos, event.button)
        elif event.type == pygame.MOUSEBUTTONUP:
            self._mouse.release(event.pos, event.button)
        elif event.type == pygame.MOUSEMOTION:
            self._mouse.move(event.pos)
        elif event.type == pygame.MOUSEWHEEL:
            self._mouse.scroll(event.y)  # positive when the wheel rolls away from you
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_TAB:
            self._mouse.show_palette = not self._mouse.show_palette

    def draw(self, canvas: pygame.Surface) -> None:
        frame = boil_frame(self._clock())
        # Games still hear about a HIDDEN piece for the grace period, but it has been peeled
        # off: there's no paper on the wall any more.
        on_desk = [p for p in self._source.latest().pieces if p.state is not PieceState.HIDDEN]
        for piece in on_desk:  # in the order they went on, so later notes lie on top
            self._note(canvas, piece.color, piece.outline, seeded(piece.id, frame), _RESTING)
        if self._mouse.show_palette:
            self._palette(canvas, frame)
            if not on_desk and self._mouse.held is None:
                self._hint(canvas, frame)
        held, outline = self._mouse.held, self._mouse.held_outline()
        if held is not None and outline is not None:
            rng = seeded(_HELD, frame)
            self._note(canvas, held.color, outline, rng, _LIFTED, alpha=_HELD_ALPHA)

    def _note(
        self,
        canvas: pygame.Surface,
        color: str,
        outline: Polygon,
        rng: random.Random,
        shadow: tuple[Point, int, int],
        alpha: int = 255,
    ) -> None:
        offset, blur, darkness = shadow
        self._shadows.draw(canvas, outline, offset, blur, darkness)
        if alpha == 255:
            _paper(canvas, color, outline, rng)
            return
        # pygame can't draw see-through shapes straight onto the canvas, so the note goes on
        # a transparent layer just big enough for it, which is laid on top at `alpha`.
        margin = 12  # pencil strokes run a few pixels past the corners
        left = math.floor(min(x for x, _ in outline)) - margin
        top = math.floor(min(y for _, y in outline)) - margin
        width = math.ceil(max(x for x, _ in outline)) - left + margin + 1
        height = math.ceil(max(y for _, y in outline)) - top + margin + 1
        layer = pygame.Surface((width, height), pygame.SRCALPHA)
        _paper(layer, color, tuple((x - left, y - top) for x, y in outline), rng)
        layer.fill((255, 255, 255, alpha), special_flags=pygame.BLEND_RGBA_MULT)
        _lay_over(canvas, layer, (left, top))

    def _palette(self, canvas: pygame.Surface, frame: int) -> None:
        palette = self._mouse.palette
        left, top, width, height = palette.bar()
        right, bottom = left + width, top + height
        tray = ((left, top), (right, top), (right, bottom), (left, bottom))
        offset, blur, darkness = _RESTING
        self._shadows.draw(canvas, tray, offset, blur, darkness)
        rng = seeded(_TRAY, frame)
        pygame.draw.polygon(canvas, TRAY, jittered(tray, rng, amount=1.5))
        pencil_outline(canvas, tray, rng)
        for i, (color, center) in enumerate(palette.swatches()):
            outline = square(center, palette.swatch)
            self._note(canvas, color, outline, seeded(_SWATCH - i, frame), _RESTING)
            if color == self._mouse.color:  # the current colour is circled in pencil
                pencil_loop(canvas, center, palette.swatch * 0.68, seeded(_CIRCLE - i, frame))

    def _hint(self, canvas: pygame.Surface, frame: int) -> None:
        """How to start, above the palette, while the desk is empty. It tilts a little
        differently every boil frame, as if written again each time."""
        text = self._font.render(HINT, True, PENCIL)
        text = pygame.transform.rotate(text, seeded(_HINT, frame).uniform(-1.2, 1.2))
        _, top, _, _ = self._mouse.palette.bar()
        _lay_over(canvas, text, text.get_rect(center=(canvas.get_width() / 2, top - 40)).topleft)


def _lay_over(canvas: pygame.Surface, image: pygame.Surface, topleft: tuple[int, int]) -> None:
    """Lay a see-through image on the canvas with premultiplied alpha.

    The canvas is often the clear overlay layer that renderers lay over their frame (ADR
    0008), and something see-through can land on something else see-through there, like the
    held note on its own shadow. pygame's ordinary blend gets that case wrong (it comes out
    darker), but premultiplied blending (src + dst * (1 - src alpha)) is right on a clear
    layer and on an opaque canvas alike. Opaque drawing and the black shadows need nothing
    special: they're already the same in premultiplied form.
    """
    canvas.blit(image.premul_alpha(), topleft, special_flags=pygame.BLEND_PREMULTIPLIED)


def _paper(surface: pygame.Surface, color: str, outline: Polygon, rng: random.Random) -> None:
    """A note of `color`: paper that wobbles with the boil, then a pencil outline over it."""
    fill = PAPER.get(color, UNKNOWN_PAPER)
    pygame.draw.polygon(surface, fill, jittered(outline, rng, amount=1.5))
    pencil_outline(surface, outline, rng)
