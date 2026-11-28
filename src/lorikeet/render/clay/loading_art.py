"""Make the loading screen's pictures: "Loading…" in clay letters, a clay track, and clay
beads that fill it as the set loads.

    uv run python -m lorikeet.render.clay.loading_art

The loading screen is shown while the clay is still being built, so it can't be clay built
live itself: it would have to load too. So it's clay rendered once, here, offscreen with
the same set, light and shader as the game, and saved as pictures (`art/`) that the loading
screen just shows. Each picture has a clear background and the soft shadow its clay would
cast on the backdrop baked in, so it sits on the set like the rest. Run this again after
changing the font or the look, and commit the pictures.
"""

from __future__ import annotations

from importlib.resources import files
from pathlib import Path

import numpy as np

from lorikeet.render.clay.clayfont import X_HEIGHT, glyph, layout
from lorikeet.render.clay.figure import Figure, Piece, build
from lorikeet.render.clay.shapes import RoundCone, Scaled

ART = files("lorikeet.render.clay").joinpath("art")
WORDS = "Loading…"
WORDS_XHEIGHT = 30.0
"""The words' x-height on the loading screen, in pixels."""

BEADS = 12
"""How many beads fill the track."""
BEAD_SPACING = 48.0
"""Pixels between the beads' middles."""
TRACK_LENGTH = BEADS * BEAD_SPACING + 24
TRACK, BEAD = (178, 164, 142), (128, 92, 64)
"""A light sandy clay track, and darker, warm brown beads (no colour a note could have)."""

SHADOW_OFFSET, SHADOW_BLUR, SHADOW_DARKNESS = (5, 7), 6, 0.38
"""The baked shadow: where it falls (right and down, as the set's light comes from the top
left), how soft it is, and how dark."""

SIZE = (1920, 1080)


def track() -> Figure:
    """A long, flat-topped roll of clay for the beads to sit in front of."""
    half = TRACK_LENGTH / 2
    bar = Scaled(RoundCone((-half, 0, 0), (half, 0, 0), 18.0, 18.0), (1.0, 0.55, 1.0))
    return Figure(
        (Piece(bar, "track"),),
        {"track": TRACK},
        lump_height=0.6,
        lump_size=14.0,
        mottle=0.05,
        mottle_size=14.0,
        seed=21,
    )


def bead(variant: int) -> Figure:
    """One bead: a short, fat roll of clay, each of a few a little different, as if rolled
    one at a time."""
    rng = np.random.default_rng(30 + variant)
    half = rng.uniform(6.5, 9.0)
    tilt = rng.uniform(-3.0, 3.0)
    radius = rng.uniform(11.0, 12.5)
    body = RoundCone((-half, 0, -tilt / 2), (half, 0, tilt / 2), radius, radius * 0.95)
    return Figure(
        (Piece(body, "bead"),),
        {"bead": BEAD},
        lump_height=0.5,
        lump_size=6.0,
        mottle=0.06,
        mottle_size=6.0,
        seed=40 + variant,
    )


def main() -> None:
    from panda3d.core import loadPrcFileData

    loadPrcFileData(
        "loading art",
        f"""
        win-size {SIZE[0]} {SIZE[1]}
        load-display p3headlessgl
        framebuffer-multisample 1
        multisamples 8
        framebuffer-alpha 1
        audio-library-name null
        textures-power-2 none
        """,
    )
    import pygame
    from direct.showbase.ShowBase import ShowBase

    from lorikeet.render.clay.cache import detail
    from lorikeet.render.clay.stage import Light, Stage, figure_node

    pygame.init()
    base = ShowBase(windowType="offscreen")
    base.disableMouse()
    window = base.win
    if window is None:
        raise SystemExit("Panda3D couldn't make an offscreen picture to render into")
    base.setBackgroundColor(0, 0, 0, 0)
    stage = Stage(base, SIZE, detail(), Light())
    stage.backdrop.hide()  # a clear background: the loading screen's own set shows behind
    out = Path(str(ART))
    out.mkdir(exist_ok=True)

    def shoot(name: str, nodes: list) -> None:
        holder = stage.root.attachNewNode(name)
        for node, (x, z), scale in nodes:
            node.reparentTo(holder)
            node.setPos(x, 0, z)
            node.setScale(scale)
        holder.setPos(SIZE[0] / 2, 0, -SIZE[1] / 2)  # the middle of the frame
        base.graphicsEngine.renderFrame()
        base.graphicsEngine.renderFrame()  # the second has the shadow map ready
        shot = window.getScreenshot()
        rgba = np.frombuffer(bytes(shot.getRamImageAs("RGBA")), dtype=np.uint8)
        image = rgba.reshape(SIZE[1], SIZE[0], 4)[::-1].astype(np.float64) / 255
        _save(_with_shadow(image), out / f"{name}.png", pygame)
        holder.removeNode()
        print("wrote", out / f"{name}.png")

    scale = WORDS_XHEIGHT / X_HEIGHT
    placed, length = layout(WORDS)
    letters = [
        (figure_node(build(glyph(char), 0.6), char), ((x - length / 2) * WORDS_XHEIGHT, 0), scale)
        for char, x in placed
    ]
    shoot("loading_words", letters)
    shoot("loading_track", [(figure_node(build(track(), 1.0), "track"), (0, 0), 1.0)])
    for variant in range(3):
        node = figure_node(build(bead(variant), 0.5), "bead")
        shoot(f"loading_bead_{variant}", [(node, (0, 0), 1.0)])


def _with_shadow(image: np.ndarray) -> np.ndarray:
    """The clay (premultiplied by its coverage, over clear) over the soft shadow it would
    cast, as straight (not premultiplied) colour and alpha, cropped to what's there."""
    import pygame

    colour, alpha = image[..., :3], image[..., 3:]
    height, width = alpha.shape[:2]
    mask = pygame.Surface((width, height), pygame.SRCALPHA)
    shadow = np.zeros((height, width, 4), dtype=np.uint8)
    dx, dy = SHADOW_OFFSET
    shadow[dy:, dx:, 3] = (alpha[: height - dy, : width - dx, 0] * 255).astype(np.uint8)
    pygame.surfarray.pixels3d(mask)[:] = 0
    pygame.surfarray.pixels_alpha(mask)[:] = shadow[..., 3].T
    blurred = pygame.transform.gaussian_blur(mask, SHADOW_BLUR)
    shade = pygame.surfarray.array_alpha(blurred).T[..., None] / 255 * SHADOW_DARKNESS
    tint = np.array([0.16, 0.13, 0.1])  # a warm dark, as the set's shadows are
    # The clay over the shadow, both premultiplied, then back to straight colour.
    out_alpha = alpha + shade * (1 - alpha)
    out_colour = colour + tint * shade * (1 - alpha)
    straight = np.where(out_alpha > 1e-4, out_colour / np.maximum(out_alpha, 1e-4), 0)
    result = np.concatenate([straight, out_alpha], axis=-1)
    seen = np.argwhere(out_alpha[..., 0] > 1 / 255)
    (top, left), (bottom, right) = seen.min(axis=0), seen.max(axis=0) + 1
    return result[top:bottom, left:right]


def _save(image: np.ndarray, path: Path, pygame) -> None:
    height, width = image.shape[:2]
    pixels = (np.clip(image, 0, 1) * 255 + 0.5).astype(np.uint8)
    surface = pygame.image.frombytes(pixels.tobytes(), (width, height), "RGBA")
    pygame.image.save(surface, str(path))


if __name__ == "__main__":
    main()
