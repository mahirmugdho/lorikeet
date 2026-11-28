"""Keeping a pygame surface (the wall, the overlay layer) on a Panda3D texture, cheaply.

The launcher hands the renderer two full-canvas pygame surfaces every frame. Converting one
to bytes the usual way (`pygame.image.tobytes`) takes about 10 ms at 1920x1080, and asking
pygame which part of a layer is drawn on (`get_bounding_rect`) about 24 ms: either would eat
most of a frame. So this reads the surface's pixels in place, without converting them:

- pygame's 32-bit surfaces keep each pixel as blue, green, red, alpha bytes, which is just
  how Panda3D keeps a texture's texels, so the pixels are copied straight across.
- pygame keeps the top row first and Panda3D the bottom row, so instead of flipping the
  rows, the card showing the texture is drawn upside down (`FLIPPED`).
- Most frames nothing has changed: the wall only changes when a note goes on or comes off,
  and the layer is usually empty. Comparing every few rows with the last copy finds any
  change bigger than a sliver in well under a millisecond, and only then is it copied (about
  3 ms, and the upload to the graphics card).
"""

from __future__ import annotations

import numpy as np
import pygame
from panda3d.core import SamplerState, Texture

FLIPPED = ((0.0, 1.0), (1.0, 0.0))
"""Texture coordinates for a card (bottom-left, top-right) that show pygame's rows right way
up: pygame's first row at the top."""


class Mirror:
    def __init__(self, name: str, size: tuple[int, int], every: int = 4) -> None:
        """A texture for `size` surfaces, compared every `every` rows to see if they've
        changed."""
        self.texture = Texture(name)
        width, height = size
        self.texture.setup2dTexture(width, height, Texture.T_unsigned_byte, Texture.F_rgba8)
        self.texture.setMinfilter(SamplerState.FT_nearest)  # shown at its own size
        self.texture.setMagfilter(SamplerState.FT_nearest)
        self._size = size
        self._every = every
        self._last: np.ndarray | None = None
        self.empty = True
        """Whether the surface was all clear (every byte 0) when last updated."""

    def update(self, surface: pygame.Surface) -> bool:
        """Copy `surface` onto the texture if it's changed. True if it was copied."""
        if not _in_place(surface, self._size):
            # Slow (about 20 ms), but only for a surface in some other pixel format.
            surface = pygame.image.frombytes(
                pygame.image.tobytes(surface, "BGRA"), self._size, "BGRA"
            )
        # Compared in 8-byte chunks (two pixels) where rows split evenly into them: fewer,
        # bigger comparisons are quicker.
        chunk = np.uint64 if self._size[0] % 2 == 0 else np.uint32
        pixels = np.frombuffer(surface.get_buffer(), dtype=chunk).reshape(self._size[1], -1)
        sample = pixels[:: self._every]
        if self._last is not None and np.array_equal(sample, self._last):
            return False
        self._last = sample.copy()
        self.empty = not pixels.any()
        memoryview(self.texture.modifyRamImage())[:] = memoryview(surface.get_buffer())
        return True


def _in_place(surface: pygame.Surface, size: tuple[int, int]) -> bool:
    """Whether the surface's pixels can be copied straight across: 32 bits, blue, green,
    red, alpha bytes in that order (on a little-endian machine), rows with no padding."""
    red, green, blue, _ = surface.get_masks()
    return (
        surface.get_size() == size
        and surface.get_bytesize() == 4
        and (red, green, blue) == (0xFF0000, 0xFF00, 0xFF)
        and surface.get_pitch() == 4 * size[0]
    )
