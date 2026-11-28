"""The words a game puts in its View (a start hint, a win message), on the clay set.

They're printed in ink on the set, like the title card of a stop-motion film: written by
pygame in the same font and inks as the flat looks, then laid over the clay picture on a
card. They go under the wall, since they're projected light too. The inks are dark and
neutral, so projected words never look like a note to the camera. Each word card has a
faint soft shadow down and to the right, the way the set's light falls, so the words sit in
the set rather than float over it, and like everything on the set they're never quite
still: each stop-motion frame they shift by up to a pixel.

Panda3D needs no window to make the cards, so this is tested without one.
"""

from __future__ import annotations

import pygame
from panda3d.core import CardMaker, NodePath, SamplerState, Texture, TransparencyAttrib

from lorikeet.render.clay.motion import jitter
from lorikeet.render.flat_looks import INK, SOFT_INK
from lorikeet.view import Text, Thing, View

SHADOW_OFFSET, SHADOW_BLUR, SHADOW_ALPHA = (3, 4), 4, 70
"""The words' shadow: how far it falls (pixels, right and down), how soft it is, and how
dark (out of 255)."""


class Words:
    def __init__(self, root: NodePath, canvas: tuple[int, int]) -> None:
        """Words go on cards under `root`, a 2D layer that spans the canvas from -1 to 1 both
        ways (as Panda3D's own 2D layer does), with up being up."""
        pygame.font.init()
        self._root = root
        self._canvas = canvas
        self._fonts: dict[int, pygame.font.Font] = {}
        self._cards: dict[int, tuple[object, NodePath]] = {}  # thing id -> (key, card)

    def show(self, view: View, frame: int = 0) -> None:
        """Put up the View's words where it says, on stop-motion frame `frame`, and take
        down any that have gone."""
        present = set()
        for thing in view.things:
            if not isinstance(thing.shape, Text):
                continue
            present.add(thing.id)
            card = self._card(thing, thing.shape)
            self._place(card, thing, frame)
        for thing_id in set(self._cards) - present:
            self._cards.pop(thing_id)[1].removeNode()

    def _card(self, thing: Thing, text: Text) -> NodePath:
        key = (text.text, round(text.size), thing.kind)
        known = self._cards.get(thing.id)
        if known is not None and known[0] == key:
            return known[1]
        if known is not None:
            known[1].removeNode()
        image = self._printed(
            text.text, round(text.size), SOFT_INK if thing.kind == "hint" else INK
        )
        texture = Texture(f"words {thing.id}")
        width, height = image.get_size()
        texture.setup2dTexture(width, height, Texture.T_unsigned_byte, Texture.F_rgba8)
        # Panda3D keeps texels bottom row first, in blue, green, red, alpha order.
        texture.setRamImage(pygame.image.tobytes(image, "BGRA", True))
        texture.setMinfilter(SamplerState.FT_linear)
        texture.setMagfilter(SamplerState.FT_linear)
        texture.setWrapU(SamplerState.WM_clamp)
        texture.setWrapV(SamplerState.WM_clamp)
        maker = CardMaker(f"words {thing.id}")
        maker.setFrame(0, 1, -1, 0)  # its top-left corner at its origin
        card = self._root.attachNewNode(maker.generate())
        card.setTexture(texture)
        card.setTransparency(TransparencyAttrib.MAlpha)  # pygame's alpha isn't premultiplied
        card.setPythonTag("size", (width, height))
        self._cards[thing.id] = (key, card)
        return card

    def _place(self, card: NodePath, thing: Thing, frame: int) -> None:
        """Centred on the thing, nudged by its jitter for this frame, its corner on a whole
        pixel so the letters stay crisp."""
        width, height = card.getPythonTag("size")
        canvas_w, canvas_h = self._canvas
        nudge = jitter(thing.id, frame)
        left = round(thing.position[0] - width / 2 + 2.5 * nudge.dx)
        top = round(thing.position[1] - height / 2 + 2.5 * nudge.dy)
        card.setPos(2 * left / canvas_w - 1, 0, 1 - 2 * top / canvas_h)
        card.setScale(2 * width / canvas_w, 1, 2 * height / canvas_h)

    def _printed(self, words: str, size: int, ink: tuple[int, int, int]) -> pygame.Surface:
        """The words in `ink` over their soft shadow, on a clear surface with room round
        them for the shadow to fade out."""
        size = max(8, size)
        if size not in self._fonts:
            self._fonts[size] = pygame.font.Font(None, size)  # None: the font pygame ships with
        font = self._fonts[size]
        letters = font.render(words, True, ink)
        pad = 3 * SHADOW_BLUR + max(SHADOW_OFFSET)
        image = pygame.Surface(
            (letters.get_width() + 2 * pad, letters.get_height() + 2 * pad), pygame.SRCALPHA
        )
        shadow = font.render(words, True, (0, 0, 0))
        shadow.set_alpha(SHADOW_ALPHA)
        soft = pygame.Surface(image.get_size(), pygame.SRCALPHA)
        soft.blit(shadow, (pad + SHADOW_OFFSET[0], pad + SHADOW_OFFSET[1]))
        image.blit(pygame.transform.gaussian_blur(soft, SHADOW_BLUR), (0, 0))
        image.blit(letters, (pad, pad))
        return image
