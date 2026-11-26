"""Lorikeet's palette: a mystical tropical night with a party on the hill.

Muted indigo backdrop, so the notes, Lori and the magenta magic pop against it. Light steps
between tones with ordered dithering; nothing is blurred or blended.
"""

from dataclasses import dataclass
from typing import Final

type RGB = tuple[int, int, int]

INK: Final[RGB] = (0x1B, 0x14, 0x33)  # outlines and text shadow, never black
CREAM: Final[RGB] = (0xFF, 0xF4, 0xE6)
WHITE_HOT: Final[RGB] = (0xFF, 0xFF, 0xFF)  # star cores, magic cores, Lori's eye shine
MUTED: Final[RGB] = (0x9A, 0x94, 0xCC)  # secondary UI text

# Night sky from the top of the screen down to the violet horizon.
NIGHT: Final[tuple[RGB, ...]] = (
    (0x0E, 0x0B, 0x26),
    (0x16, 0x10, 0x38),
    (0x20, 0x16, 0x4A),
    (0x2C, 0x1D, 0x5C),
)
STARS: Final[tuple[RGB, ...]] = (WHITE_HOT, (0xB8, 0xB0, 0xE8), (0x6E, 0x64, 0xB0))

# Silhouettes: far hills, the hillside houses, the near canopy. Windows glow dim or party-lit.
HILLS: Final[tuple[RGB, ...]] = ((0x26, 0x1C, 0x56), (0x1C, 0x15, 0x44), (0x13, 0x0E, 0x30))
WINDOW_DIM: Final[RGB] = (0x33, 0x29, 0x6E)
PARTY: Final[tuple[RGB, ...]] = (  # amber, pink, cyan, lime: bulbs, lit windows, confetti
    (0xFF, 0xC5, 0x6B),
    (0xFF, 0x7A, 0xD9),
    (0x7C, 0xF0, 0xFF),
    (0x9C, 0xF0, 0x7A),
)
PARTY_DIM: Final[tuple[RGB, ...]] = (
    (0x7A, 0x55, 0x3A),
    (0x7A, 0x3A, 0x6E),
    (0x3A, 0x6E, 0x80),
    (0x44, 0x70, 0x3E),
)
WIRE: Final[RGB] = (0x2C, 0x25, 0x60)

# Stone tiles for ledges and the ground strip: lit edge, top course, body, seams.
STONE: Final[tuple[RGB, ...]] = (
    (0x4A, 0x41, 0x80),
    (0x33, 0x2B, 0x68),
    (0x26, 0x20, 0x52),
    (0x19, 0x14, 0x3C),
)
TWIG: Final[tuple[RGB, RGB]] = ((0xC0, 0x74, 0x4A), (0x8A, 0x4C, 0x36))  # the nest

# Magic: outer glow dots, inner glow, the bright ring, the hot core.
MAGIC: Final[tuple[RGB, ...]] = (
    (0x3A, 0x22, 0x7A),
    (0x8A, 0x3A, 0xC8),
    (0xFF, 0x5A, 0xE0),
    (0xFF, 0xC8, 0xF6),
)
SMOKE: Final[tuple[RGB, RGB]] = ((0xC9, 0xC1, 0xE6), (0x8E, 0x86, 0xB8))


@dataclass(frozen=True)
class Ramp:
    """A note colour: `light` for the top highlight, `dark` for the bottom edge and curl."""

    light: RGB
    base: RGB
    dark: RGB


SKY: Final = Ramp((0xB0, 0xD0, 0xFF), (0x6F, 0xA8, 0xFF), (0x3C, 0x68, 0xC8))
LEAF: Final = Ramp((0xAA, 0xF5, 0xC4), (0x6B, 0xE3, 0x9A), (0x30, 0x96, 0x64))
SUN: Final = Ramp((0xFF, 0xEC, 0x96), (0xFF, 0xD9, 0x5A), (0xD6, 0xA0, 0x28))  # from note.png
EMBER: Final = Ramp((0xFF, 0xB0, 0x96), (0xFF, 0x7A, 0x59), (0xC4, 0x48, 0x3C))
DUSK: Final = Ramp((0xD6, 0xC0, 0xFF), (0xB4, 0x8C, 0xFF), (0x78, 0x58, 0xC8))

RAMPS: Final[dict[str, Ramp]] = {
    "sky": SKY,
    "leaf": LEAF,
    "sun": SUN,
    "ember": EMBER,
    "dusk": DUSK,
}

# The egg: cream shell, lilac shade toward the lower right, blue and violet speckles.
EGG: Final = Ramp(CREAM, (0xE6, 0xD8, 0xF0), (0xA8, 0x9C, 0xD8))

ALL: Final[frozenset[RGB]] = frozenset(
    {INK, CREAM, WHITE_HOT, MUTED, WINDOW_DIM, WIRE}
    | {*NIGHT, *STARS, *HILLS, *PARTY, *PARTY_DIM, *STONE, *TWIG, *MAGIC, *SMOKE}
    | {c for r in (*RAMPS.values(), EGG) for c in (r.light, r.base, r.dark)}
)
