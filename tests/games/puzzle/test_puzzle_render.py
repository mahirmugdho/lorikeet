"""The look contract.

Sharp layers (the backdrop before it's defocused, the playfield ledges, every sprite) are pure
pixel art: palette colours only, each art pixel a solid k x k block. The backdrop is then
deliberately blurred behind the action, and soft light is blended over everything; that mix
is the intended look, so the finished frame isn't held to the pixel rule.
"""

import os
from collections.abc import Iterator

import numpy as np
import pygame
import pytest

from lorikeet.games.puzzle import palette as pal
from lorikeet.games.puzzle.app import Game, Mode
from lorikeet.games.puzzle.level import BOARD_H, BOARD_W, load_level
from lorikeet.games.puzzle.render import Renderer
from lorikeet.games.puzzle.sim import PlacedNote
from lorikeet.games.puzzle.sprites import Sprites

SCALE = 4


@pytest.fixture(scope="module")
def sprites() -> Iterator[Sprites]:
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")  # CI has no display
    pygame.display.init()
    pygame.font.init()
    pygame.display.set_mode((BOARD_W, BOARD_H))
    yield Sprites.load()
    pygame.quit()


@pytest.fixture(scope="module")
def renderer(sprites: Sprites) -> Renderer:
    return Renderer(sprites, load_level("1-1"), SCALE)


def colours(surface: pygame.Surface) -> set[tuple[int, int, int]]:
    """Distinct opaque colours. Packs RGB into one int so np.unique stays fast."""
    rgb = pygame.surfarray.array3d(surface).reshape(-1, 3).astype(np.int64)
    if surface.get_flags() & pygame.SRCALPHA:
        rgb = rgb[pygame.surfarray.array_alpha(surface).reshape(-1) == 255]
    packed = np.unique((rgb[:, 0] << 16) | (rgb[:, 1] << 8) | rgb[:, 2])
    return {(int(c) >> 16, (int(c) >> 8) & 255, int(c) & 255) for c in packed}


def allowed(s: Sprites) -> set[tuple[int, int, int]]:
    """The palette plus every colour hand-placed in a sprite. Anything else was blended."""
    sparks = [f for v in s.sparks.values() for f in v]
    art = [*s.lori, s.note, s.wordmark, s.nest, s.blossom, s.mushroom, *s.egg, *sparks]
    return set(pal.ALL).union(*(colours(a) for a in art))


def chunky(img: pygame.Surface, k: int) -> bool:
    """True when every k x k block of `img` is one colour."""
    px = pygame.surfarray.array3d(img)
    w, h = img.get_width() // k, img.get_height() // k
    blocks = px[: w * k, : h * k].reshape(w, k, h, k, 3)
    return bool((blocks == blocks[:, :1, :, :1, :]).all())


def test_frames_fill_the_window(sprites: Sprites, renderer: Renderer) -> None:
    level = load_level("1-1")
    game = Game(level)
    assert renderer.draw(game).get_size() == (BOARD_W * SCALE, BOARD_H * SCALE)
    game.set_mode(Mode.BUILD)
    game.placed = [PlacedNote(*n) for n in level.solution]
    game.held = PlacedNote("sun", 150, 80, 45)
    game.drop()
    for _ in range(400):
        game.update()
        frame = renderer.draw(game)
        if game.mode is not Mode.PLAY:
            break
    assert game.mode is Mode.WON
    for _ in range(4 * 120):  # the whole nectar burst, the confetti and the settle
        game.update()
        frame = renderer.draw(game)
    assert frame.get_size() == (BOARD_W * SCALE, BOARD_H * SCALE)


def test_sharp_layers_are_palette_pixel_art(sprites: Sprites, renderer: Renderer) -> None:
    ok = allowed(sprites)
    for name, img in (("backdrop", renderer.scene.image), ("title", renderer.title.image)):
        stray = colours(img) - ok
        assert not stray, f"{name}: blended colours {sorted(stray)[:5]}"
    for img, _ in renderer.play:
        assert not colours(img) - ok, "a playfield piece has blended colours"
        assert chunky(img, SCALE), "a playfield piece isn't whole chunky pixels"


def test_backdrop_is_out_of_focus(renderer: Renderer) -> None:
    """The defocused backdrop is soft: far more in-between colours than the sharp original."""
    sharp, soft = colours(renderer.scene.image), colours(renderer.back)
    assert len(soft) > 20 * len(sharp)
    assert not chunky(renderer.back, SCALE)


def test_sprites_scale_to_whole_chunky_pixels(sprites: Sprites, renderer: Renderer) -> None:
    """Smooth motion moves sprites; it must never smear them. Each art pixel stays a k x k block."""
    for art in (sprites.lori[0], sprites.egg[5], sprites.note, sprites.blossom):
        assert chunky(renderer.big(art), SCALE)


def test_every_homing_spark_comes_home(sprites: Sprites) -> None:
    """The pickup sparks must all curve back into the blossom, none left wandering."""
    from lorikeet.games.puzzle import fx

    plan = fx.homing_sparks()
    for path in plan.paths:
        assert path[-1] is None, "a spark was still flying when the win settled"
        last = next(p for p in reversed(path) if p is not None)
        assert (last[0] ** 2 + last[1] ** 2) ** 0.5 < 6


def test_shield_is_palette_pixel_art(sprites: Sprites) -> None:
    from lorikeet.games.puzzle import fx

    for t in (0.05, 0.2, 0.4, 0.6):
        assert colours(fx.hex_shield(9, t, gone=0.65)) <= set(pal.ALL)
