"""Run the puzzle prototype: `uv run python -m lorikeet.games.puzzle [--fps]`.

`--screenshot out.png [--scene build|play|fail --frames N]` renders one tick without a window.
`--sprites out.png` saves the new sprites at x10 for review.
"""

import argparse
import os
from pathlib import Path

import pygame

from .app import TICKS_PER_SECOND, Game, Mode
from .level import BOARD_H, BOARD_W, load_level
from .render import Renderer
from .sim import PlacedNote
from .sprites import Sprites, sprite_sheet, text


def stage(game: Game, scene: str) -> None:
    """Set up a scene for a screenshot, using the level's known solution."""
    if scene == "title":
        return
    game.set_mode(Mode.BUILD)
    if scene != "fail":
        game.placed = [PlacedNote(*n) for n in game.level.solution]
    if scene in ("play", "fail"):
        game.drop()


def auto_scale() -> int:
    """The largest whole-number scale of the board that fits the screen with room to spare."""
    w, h = pygame.display.get_desktop_sizes()[0]
    return max(1, min(w // BOARD_W, (h - 80) // BOARD_H))


def open_window(scale: int) -> tuple[pygame.Surface, bool]:
    """A window at `scale` x the board. SCALED lets SDL present it with vsync; at this size SDL
    adds no scaling of its own, and nearest-neighbour is forced in case it ever does.

    Returns the surface to draw on and whether vsync took.
    """
    os.environ.setdefault("SDL_RENDER_SCALE_QUALITY", "0")
    size = (BOARD_W * scale, BOARD_H * scale)
    try:
        return pygame.display.set_mode(size, pygame.SCALED, vsync=1), True
    except pygame.error:
        return pygame.display.set_mode(size, pygame.SCALED), False


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="python -m lorikeet.games.puzzle")
    p.add_argument("--level", default="1-1")
    p.add_argument("--scale", type=int, help="whole-number scale (default: fit the screen)")
    p.add_argument("--screenshot", type=Path)
    p.add_argument("--scene", choices=("title", "build", "play", "fail"), default="title")
    p.add_argument("--frames", type=int, default=0, help="ticks (1/120 s) before the shot")
    p.add_argument("--sprites", type=Path)
    p.add_argument("--fps", action="store_true", help="show the frame rate in the corner")
    args = p.parse_args(argv)
    headless = bool(args.screenshot or args.sprites)
    if headless:
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

    pygame.init()
    scale = args.scale or (4 if headless else auto_scale())
    if headless:
        window, vsync = pygame.display.set_mode((BOARD_W, BOARD_H)), False
    else:
        window, vsync = open_window(scale)
    pygame.display.set_caption("lorikeet")
    sprites = Sprites.load()
    level = load_level(args.level)
    game = Game(level)
    renderer = Renderer(sprites, level, scale)

    if args.sprites:
        pygame.image.save(sprite_sheet(sprites), args.sprites)
        return
    if args.screenshot:
        stage(game, args.scene)
        for _ in range(args.frames):
            game.update()
        pygame.image.save(renderer.draw(game), args.screenshot)
        return

    # One game tick per screen refresh: 1 on a 120 Hz display, 2 on a 60 Hz one. Locking ticks
    # to refreshes avoids the judder a time accumulator gets from 0-or-2-tick frames.
    hz = (pygame.display.get_desktop_refresh_rates() or [60])[0] or 60
    ticks_per_frame = max(1, round(TICKS_PER_SECOND / hz))
    clock = pygame.time.Clock()
    while True:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT or (ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE):
                pygame.quit()
                return
            game.handle(ev, scale)
        for _ in range(ticks_per_frame):
            game.update()
        window.blit(renderer.draw(game), (0, 0))
        if args.fps:
            label = f"{clock.get_fps():.0f} fps · {hz} hz{'' if vsync else ' no vsync'}"
            img = text(sprites.font, label, (255, 255, 255))
            window.blit(pygame.transform.scale_by(img, scale), (4 * scale, (BOARD_H - 9) * scale))
        pygame.display.flip()  # waits for the refresh when vsync took
        clock.tick(0 if vsync else hz)


if __name__ == "__main__":
    main()
