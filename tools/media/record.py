"""Record the puzzle prototype's README/PR GIFs headlessly into docs/media/.

Run: uv run --with pillow python tools/media/record.py

Every GIF is the real renderer driving the real game state (no mock-ups): the scripted
"player" drags a note out of the pad, turns it, and drops the egg, exactly as the mouse would.
Frames are taken every 5 game ticks (24 per second) and played at 40 ms.
"""

import os
from collections.abc import Callable, Iterator
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame
from PIL import Image

from lorikeet.games.puzzle.app import TICKS_PER_SECOND, Game, Mode
from lorikeet.games.puzzle.level import BOARD_H, BOARD_W, load_level
from lorikeet.games.puzzle.render import POP, Renderer
from lorikeet.games.puzzle.sim import PlacedNote
from lorikeet.games.puzzle.sprites import Sprites

OUT = Path(__file__).resolve().parents[2] / "docs" / "media"
EVERY = 5  # ticks per GIF frame
FRAME_MS = 40

Frame = pygame.Surface
Crop = tuple[int, int, int, int] | None


def ticks(game: Game, n: int) -> Iterator[None]:
    for _ in range(n):
        game.update()
        yield


def seconds(s: float) -> int:
    return round(s * TICKS_PER_SECOND)


def record(
    name: str,
    script: Callable[[Game], Iterator[None]],
    scale: int = 2,
    crop: Crop = None,
) -> None:
    level = load_level("1-1")
    game = Game(level)
    renderer = Renderer(Sprites.load(), level, scale)
    images: list[Image.Image] = []
    for i, _ in enumerate(script(game)):
        if i % EVERY:
            continue
        frame: Frame = renderer.draw(game)
        if crop is not None:
            frame = frame.subsurface(crop)
        rgb = Image.frombytes("RGB", frame.get_size(), pygame.image.tobytes(frame, "RGB"))
        images.append(
            rgb.quantize(colors=255, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
        )
    path = OUT / f"{name}.gif"
    images[0].save(
        path, save_all=True, append_images=images[1:], duration=FRAME_MS, loop=0, disposal=1
    )
    size_mb = path.stat().st_size / 1e6
    print(f"{path.relative_to(OUT.parents[1])}: {len(images)} frames, {size_mb:.1f} MB")


def title(game: Game) -> Iterator[None]:
    yield from ticks(game, seconds(3.0))


def drag_and_drop(game: Game, scale: int) -> Iterator[None]:
    """Drag a Sun note from the pad to the level's known solution, turning it on the way."""
    color, x, y, angle = game.level.solution[0]
    slot = game.pad_slots()[0][1]
    sx, sy = slot.center
    game.press_at(sx, sy)
    steps = seconds(0.9)
    turns = angle // 15
    for i in range(steps + 1):
        u = i / steps
        e = 1 - (1 - u) ** 3  # ease out, like a hand settling
        px, py = sx + (x - sx) * e, sy + (y - sy) * e
        game.cursor = (round(px), round(py))
        game.pointer = (round(px * scale), round(py * scale))
        if turns and i in {round(steps * (0.3 + 0.2 * t)) for t in range(turns)}:
            game.rotate(1)
        game.update()
        yield
    game.release(x, y)
    assert game.placed[-1].angle == angle and game.placed[-1].color == color


def first_hop(game: Game) -> Iterator[None]:
    game.set_mode(Mode.BUILD)
    yield from ticks(game, seconds(0.5))
    yield from drag_and_drop(game, 2)
    yield from ticks(game, seconds(0.4))
    game.drop()
    while game.mode is Mode.PLAY:
        game.update()
        yield
    yield from ticks(game, POP + seconds(1.6))


def splat_and_ghost(game: Game) -> Iterator[None]:
    game.set_mode(Mode.BUILD)
    yield from ticks(game, seconds(0.3))
    game.drop()  # no notes: the egg rolls off the nest ledge and splats
    while game.mode is not Mode.BUILD:
        game.update()
        yield
    yield from ticks(game, seconds(1.6))  # the ghost of that run draws itself on


def hatch(game: Game) -> Iterator[None]:
    """Close-up: the egg rolls up to the blossom, is taken in, and hatches."""
    game.set_mode(Mode.BUILD)
    game.placed = [PlacedNote(*n) for n in game.level.solution]
    game.drop()
    while game.mode is Mode.PLAY:
        game.update()
        if game.egg_pos[0] > game.level.blossom[0] - 40:  # start once it's in the shot
            yield
    yield from ticks(game, POP + seconds(1.4))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    pygame.display.init()
    pygame.font.init()
    pygame.display.set_mode((BOARD_W, BOARD_H))
    record("title", title)
    record("first-hop", first_hop)
    record("splat-and-ghost", splat_and_ghost)
    bx, by = load_level("1-1").blossom
    record("hatch", hatch, scale=4, crop=(bx * 4 - 300, by * 4 - 170, 400, 260))


if __name__ == "__main__":
    main()
