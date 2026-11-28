"""The loading screen: "Loading…" over a clay track that fills with clay beads.

Its pictures are clay rendered ahead of time (`loading_art.py`), so the screen shows the
moment it's needed, with nothing of its own to load. Like everything on the set it's never
quite still: each piece shifts by up to a pixel each stop-motion frame, and each bead pops
in a little big on the frame it arrives.

Panda3D needs no window to make the cards, so this is tested without one.
"""

from __future__ import annotations

from importlib.resources import files

import pygame
from panda3d.core import CardMaker, NodePath, SamplerState, Texture, TransparencyAttrib

from lorikeet.render.clay.loading_art import BEAD_SPACING, BEADS
from lorikeet.render.clay.motion import jitter

ART = files("lorikeet.render.clay").joinpath("art")
WORDS_UP, TRACK_DOWN = 70.0, 50.0
"""Where the words and the track are, in pixels above and below the canvas's middle."""
POP = 1.25
"""How big a bead is on the frame it arrives."""
NUDGE = 2.5
"""Jitter (up to about 0.4) times this is how far a piece shifts each frame, in pixels."""


class LoadingScreen:
    def __init__(self, root: NodePath, canvas: tuple[int, int]) -> None:
        """Cards under `root`, a 2D layer spanning the canvas from -1 to 1 both ways."""
        self._root = root.attachNewNode("loading screen")
        self._canvas = canvas
        width, height = canvas
        middle = (width / 2, height / 2)
        self._words = self._card("loading_words", (middle[0], middle[1] - WORDS_UP))
        track_at = (middle[0], middle[1] + TRACK_DOWN)
        self._track = self._card("loading_track", track_at)
        self._beads = [
            self._card(
                f"loading_bead_{i % 3}",
                (track_at[0] + (i - (BEADS - 1) / 2) * BEAD_SPACING, track_at[1] - 3),
            )
            for i in range(BEADS)
        ]
        self._arrived: list[int | None] = [None] * BEADS  # the frame each bead arrived
        self._root.hide()

    def show(self, visible: bool, beads: int, frame: int) -> None:
        """Show the screen with `beads` beads on the track, on stop-motion frame `frame`,
        or hide it."""
        if not visible:
            self._root.hide()
            return
        self._root.show()
        for i, card in enumerate((self._words, self._track, *self._beads)):
            self._place(card, frame, i)
        for i, card in enumerate(self._beads):
            if i >= beads:
                card.hide()
                continue
            card.show()
            if self._arrived[i] is None:
                self._arrived[i] = frame
            if self._arrived[i] == frame:
                self._place(card, frame, i + 2, grow=POP)

    def _card(self, name: str, centre: tuple[float, float]) -> NodePath:
        image = pygame.image.load(str(ART.joinpath(f"{name}.png")))
        width, height = image.get_size()
        texture = Texture(name)
        texture.setup2dTexture(width, height, Texture.T_unsigned_byte, Texture.F_rgba8)
        # Panda3D keeps texels bottom row first, in blue, green, red, alpha order.
        texture.setRamImage(pygame.image.tobytes(image, "BGRA", True))
        texture.setMinfilter(SamplerState.FT_linear)
        texture.setMagfilter(SamplerState.FT_linear)
        texture.setWrapU(SamplerState.WM_clamp)
        texture.setWrapV(SamplerState.WM_clamp)
        maker = CardMaker(name)
        maker.setFrame(-0.5, 0.5, -0.5, 0.5)  # round its middle, so it can grow from there
        card = self._root.attachNewNode(maker.generate())
        card.setTexture(texture)
        card.setTransparency(TransparencyAttrib.MAlpha)  # straight alpha, as PNGs keep it
        card.setPythonTag("size", (width, height))
        card.setPythonTag("centre", centre)
        return card

    def _place(self, card: NodePath, frame: int, which: int, grow: float = 1.0) -> None:
        """At its spot, nudged by its jitter for this frame, on whole pixels so it stays
        crisp (and `grow` times its size)."""
        width, height = card.getPythonTag("size")
        x, y = card.getPythonTag("centre")
        nudge = jitter(9000 + which, frame)
        left = round(x - width / 2 + NUDGE * nudge.dx)
        top = round(y - height / 2 + NUDGE * nudge.dy)
        canvas_w, canvas_h = self._canvas
        card.setPos(2 * (left + width / 2) / canvas_w - 1, 0, 1 - 2 * (top + height / 2) / canvas_h)
        card.setScale(2 * width * grow / canvas_w, 1, 2 * height * grow / canvas_h)
