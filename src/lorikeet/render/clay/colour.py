"""Colours in linear light, so the lighting maths is right and the colours stay vivid.

Colours are usually written as sRGB (0-255), which isn't proportional to light: sRGB 128 is
only about 22% as bright as 255, not 50%. The eye is more sensitive to differences in dark
tones, so sRGB spends more of its 256 steps there.

Light adds up in physical units, so the clay shader does all its lighting in *linear*
values (proportional to light) and converts back to sRGB only at the very end. Done the
other way round, mixing lit and shadowed colour gives muddy, too-dark midtones and harsh
falloffs. Done this way, gradients stay soft and colours stay clean.
"""

from __future__ import annotations


def linear(srgb: tuple[int, int, int]) -> tuple[float, float, float]:
    """An sRGB colour (0-255 each) as linear light (0-1 each)."""
    r, g, b = (_to_linear(c / 255.0) for c in srgb)
    return r, g, b


def _to_linear(c: float) -> float:
    # The exact sRGB curve: a short straight part near black, then a 2.4 power.
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def srgb(light: tuple[float, float, float]) -> tuple[int, int, int]:
    """Linear light (0-1 each) back to sRGB (0-255 each)."""
    r, g, b = (round(255 * _to_srgb(min(max(c, 0.0), 1.0))) for c in light)
    return r, g, b


def _to_srgb(c: float) -> float:
    return 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055
