"""Draw a frame: chunky pixel art that moves smoothly, under soft light, with a camera focus.

Back to front:

1. **Backdrop, out of focus**: the night sky, hills and houses are pixel art on the 320 x 180
   board, scaled up, blurred and tinted once per scene so they sit behind the action. Their
   lights (stars, party windows, string bulbs) are drawn as soft bokeh that fades slowly.
2. **Playfield, in focus**: ledges, mushrooms and the pad strip, crisp chunky pixels.
3. **Sprites**: every sprite is pre-scaled to the same chunky pixels, then placed at sub-pixel
   positions, so motion is smooth instead of stepping a whole art pixel at a time.
4. **Light**: slow, breathing additive glows and a vignette, then crisp UI text.

Every light changes on a slow sine, measured in seconds, never by flicking on and off.
"""

import math
import random
from collections.abc import Callable
from dataclasses import dataclass, field
from itertools import pairwise

import numpy as np
import pygame

from . import fx
from . import palette as pal
from .app import (
    DROP_BUTTON,
    POP_TICKS,
    PRESS_TICKS,
    TICKS_PER_SECOND,
    TRAIL_LIFE,
    Burst,
    Game,
    Mode,
    Peel,
    Splat,
)
from .dither import vertical
from .level import BOARD_H, BOARD_W, PAD_TOP, Level
from .sim import Outcome, PlacedNote
from .sprites import BLINK, EGG_BOX, IDLE_CYCLE, SQUASH_HARD, SQUASH_SOFT, Sprites, ledge, text

TAGLINE = "stick · tumble · fly"
LORI_ANCHOR = (12, 15)  # sprite pixel at Lori's centre (the level's nest point)
NEST_FOOT = 9  # px from Lori's centre down to the shelf she sits on
EGG_BEHIND_TICKS = 18  # the egg rises from behind Lori before it clears the nest
BULB_GAP = 14
TITLE_SPARKS = [(92, 44, "p", 0), (222, 52, "b", 8), (70, 100, "v", 14),
                (250, 96, "p", 20), (112, 140, "b", 5), (206, 136, "y", 17)]  # fmt: skip
BURST_OFFSETS = [(-6, -4), (5, -6), (-3, 4), (6, 3), (0, -8), (-8, 1)]
SMOKE_OFFSETS = [(-4, 0), (3, -2), (0, -5)]
LEVELS = 12  # brightness steps for every fading light; enough that the steps don't show
FLASH_TICKS = 36

# Slow rhythms, in ticks (120 per second).
GLOW_BREATH = 480  # orb glows breathe in and out every 4 s
BULB_WAVE = 420  # a soft brightness wave rolls along the string lights
WINDOW_FADE = 480  # each party window fades to a new colour every 4 s
TITLE_BOB = 360

# The nectar burst when the egg reaches the blossom, in ticks from the win.
# The win, in ticks from the egg touching the blossom (pickup + shield grammar):
LIFT = 12  # the egg lifts and stretches...
FLY = 41  # ...then arcs into the orb's centre, speeding up
ARRIVE = LIFT + FLY
CONTRACT = ARRIVE + 58  # a hex shield forms around it, then closes in
POP = ARRIVE + 78  # squash, white stretch, blink out
SHATTER = 54  # ticks the burst bubble's fragments fly for
CELEBRATE = POP + 30  # confetti and "nectar!"
HATCH = 6  # ticks after the pop when the chick appears where the egg blinked out
SHIELD_R = 9.0
SPARK_TONES = (pal.WHITE_HOT, pal.MAGIC[3], pal.SUN.light)


@dataclass
class Night:
    """A sharp board-resolution backdrop, plus the lights in it that animate."""

    image: pygame.Surface
    twinkles: list[tuple[int, int, int]] = field(default_factory=list)  # (x, y, phase)
    windows: list[tuple[int, int, int]] = field(default_factory=list)  # party windows
    bulbs: list[tuple[int, int]] = field(default_factory=list)
    lamps: list[tuple[int, int]] = field(default_factory=list)  # glowing mushrooms


def night(seed: int = 7, drop: int = 0) -> Night:
    """A tropical night: dithered sky, stars, far hills, a hillside of houses, the near canopy,
    and a string of party lights. Seeded, so the same scene every run. `drop` lowers the hills.
    """
    rng = random.Random(seed)
    rgb = np.array(pal.NIGHT, dtype=np.uint8)[vertical(BOARD_W, BOARD_H, 0.0, 0.8, 4)]
    scene = Night(image=pygame.Surface((1, 1)))

    for _ in range(150):
        x, y = rng.randrange(BOARD_W), rng.randrange(118)
        roll = rng.random()
        rgb[y, x] = pal.STARS[0] if roll < 0.1 else pal.STARS[1] if roll < 0.4 else pal.STARS[2]
        if roll < 0.15 and len(scene.twinkles) < 18:
            scene.twinkles.append((x, y, rng.randrange(1000)))

    xs = np.arange(BOARD_W, dtype=np.float64)
    far = np.round(drop + 104 + 7 * np.sin(xs * 0.02 + 0.5) + 4 * np.sin(xs * 0.061 + 2))
    hill = np.round(drop + 130 + 9 * np.sin(xs * 0.015 + 1.2) + 4 * np.sin(xs * 0.05))
    near = np.round(drop + 151 - 8 * np.abs(np.sin(xs * 0.06 + 0.7)) + 2 * np.sin(xs * 0.017))
    for col in range(BOARD_W):
        rgb[int(far[col]) :, col] = pal.HILLS[0]
        rgb[int(hill[col]) :, col] = pal.HILLS[1]

    # Hillside houses: boxes stepping along the hill, windows on a 3 px grid.
    x = 0
    while x < BOARD_W:
        w, h = rng.randint(7, 13), rng.randint(5, 13)
        top = int(hill[min(x + w // 2, BOARD_W - 1)]) - h
        x1 = min(x + w, BOARD_W)
        if top < BOARD_H:
            rgb[top:, x:x1] = pal.HILLS[1]
            rgb[top, x:x1] = pal.HILLS[0]  # moonlit roof edge
        for wy in range(top + 2, min(top + h + 4, BOARD_H), 3):
            for wx in range(x + 2, x1 - 1, 3):
                roll = rng.random()
                if roll < 0.06:
                    scene.windows.append((wx, wy, rng.randrange(8)))
                elif roll < 0.24:
                    rgb[wy, wx] = rng.choice(pal.PARTY)
                else:
                    rgb[wy, wx] = pal.WINDOW_DIM
        x += w + rng.randint(0, 2)

    for col in range(BOARD_W):
        rgb[int(near[col]) :, col] = pal.HILLS[2]

    for col in range(BOARD_W):  # string lights: a sagging wire, bulbs hung along it
        rgb[_wire_y(col), col] = pal.WIRE
    scene.bulbs = [(bx, _wire_y(bx) + 1) for bx in range(7, BOARD_W, BULB_GAP)]

    scene.image = pygame.surfarray.make_surface(rgb.swapaxes(0, 1)).convert()
    return scene


def _wire_y(x: int) -> int:
    sag = 18 * (1 - ((x - 160) / 172) ** 2)
    return round(26 - 6 * x / BOARD_W + sag)


def _wave(tick: int, period: int, phase: float = 0.0) -> float:
    """0..1 on a slow sine."""
    return 0.5 + 0.5 * math.sin(2 * math.pi * tick / period + phase)


def _level(v: float) -> int:
    """A 0..1 brightness as an index into a LEVELS-long list of pre-built lights."""
    return min(LEVELS - 1, max(0, int(v * LEVELS)))


class Renderer:
    def __init__(self, sprites: Sprites, level: Level, scale: int = 4) -> None:
        self.s = sprites
        self.level = level
        self.k = k = scale
        self.frame = pygame.Surface((BOARD_W * k, BOARD_H * k))
        blur = max(1, round(0.6 * k))  # about half an art pixel out of focus: soft, not smeared

        self.title = night(drop=26)  # keep the hillside clear of the title text
        self.title_back = fx.defocus(self.title.image, k, blur)
        self.title_orb = fx.orb(22, 0)
        self.title_play = [
            (pygame.transform.scale_by(ledge(BOARD_W, 14), k), (0, (BOARD_H - 14) * k))
        ]

        self.scene = night()
        self.back = fx.defocus(self.scene.image, k, blur)
        self.play: list[tuple[pygame.Surface, tuple[int, int]]] = []
        for r in level.terrain:
            self.play.append((pygame.transform.scale_by(ledge(r.w, r.h), k), (r.x * k, r.y * k)))
            if r.w >= 30:  # a glowing mushroom near each end of a wide shelf
                for mx in (r.x + 8, r.x + r.w - 11):
                    if not _near_nest(mx, r.y, level):
                        mush = pygame.transform.scale_by(sprites.mushroom, k)
                        self.play.append((mush, (mx * k, (r.y - 3) * k)))
                        self.scene.lamps.append((mx + 1, r.y - 2))
        pad = ledge(BOARD_W, BOARD_H - PAD_TOP)
        self.play.append((pygame.transform.scale_by(pad, k), (0, PAD_TOP * k)))

        def steps(make: Callable[[float], pygame.Surface]) -> list[pygame.Surface]:
            """One pre-built light per brightness step, dimmest first."""
            return [make((i + 1) / LEVELS) for i in range(LEVELS)]

        self.star_bokeh = steps(lambda v: fx.bokeh(round(1.2 * k), pal.WHITE_HOT, 0.95 * v))
        self.bulb_bokeh = [
            steps(lambda v, c=c: fx.bokeh(round(1.7 * k), c, 0.3 + 0.7 * v)) for c in pal.PARTY
        ]
        self.bulb_halo = [steps(lambda v, c=c: fx.soft_glow(6 * k, c, 0.3 * v)) for c in pal.PARTY]
        self.window_bokeh = [
            steps(lambda v, c=c: fx.bokeh(round(1.0 * k), c, 0.85 * v)) for c in pal.PARTY
        ]
        self.glow_orb = steps(lambda v: fx.soft_glow(26 * k, pal.MAGIC[2], 0.2 + 0.12 * v))
        self.glow_title = steps(lambda v: fx.soft_glow(46 * k, pal.MAGIC[2], 0.18 + 0.1 * v))
        self.glow_lamp = steps(lambda v: fx.soft_glow(7 * k, pal.PARTY[2], 0.2 + 0.2 * v))
        self.glow_flash = steps(lambda v: fx.soft_glow(16 * k, pal.MAGIC[3], 0.55 * v))
        self.glow_egg = fx.soft_glow(16 * k, pal.MAGIC[3], 0.3)
        self.glow_burst = steps(lambda v: fx.soft_glow(36 * k, pal.MAGIC[3], 0.6 * v))
        self.glow_spark = steps(lambda v: fx.soft_glow(4 * k, pal.MAGIC[3], 0.45 * v))
        rng = random.Random(23)  # the win plays the same every time
        self.petals = [
            (-math.pi / 2 + rng.uniform(-1.3, 1.3), rng.uniform(35, 80), i % 2) for i in range(10)
        ]
        self.spark_plan = fx.homing_sparks()
        self.shards = [  # the burst bubble: ring arcs and the glow dots inside it
            (
                j * 2 * math.pi / 10 + rng.uniform(-0.12, 0.12),
                rng.uniform(0.35, 0.5),
                rng.uniform(-0.6, 0.6),
            )
            for j in range(10)
        ]
        self.motes_in = [
            (rng.uniform(0, 2 * math.pi), rng.uniform(1.5, 8.5), rng.uniform(40, 90))
            for _ in range(18)
        ]
        self.vignette = fx.vignette(BOARD_W * k, BOARD_H * k, 0.38)
        dim = pal.NIGHT[3]
        self.prompt_shades: list[pal.RGB] = [
            _mix(dim, pal.MUTED, 0.5 + 0.5 * i / (LEVELS - 1)) for i in range(LEVELS)
        ]

        self._big: dict[int, pygame.Surface] = {}
        self._notes: dict[int, pygame.Surface] = {}
        self._texts: dict[tuple[str, pal.RGB, int], pygame.Surface] = {}

    def draw(self, game: Game) -> pygame.Surface:
        """The finished frame at window resolution."""
        if game.mode is Mode.TITLE:
            self._title(game)
        else:
            self._level(game)
        return self.frame

    # -- screens ----------------------------------------------------------------------------

    def _title(self, game: Game) -> None:
        t = game.tick
        self.frame.blit(self.title_back, (0, 0))
        self._backdrop_lights(self.title, t)
        for img, pos in self.title_play:
            self.frame.blit(img, pos)
        self._put_c(self.title_orb, 160, 84)
        self._sparkles(t, TITLE_SPARKS)
        bob = 1.2 * math.sin(2 * math.pi * t / TITLE_BOB)  # Lori and her note float gently
        self._put(self.s.note, 149, 96 + bob)
        self._put(self.s.lori[self._idle(t)], 148, 72 + bob)
        self._add(self.glow_title[_level(_wave(t, GLOW_BREATH))], 160, 84)
        self._finish()
        self._put(self.s.wordmark, 136, 112)
        self._centered(TAGLINE, 128, colour=pal.MUTED)
        shade = self.prompt_shades[_level(_wave(t, 300))]  # a slow fade, not a blink
        self._centered("space to start", 143, colour=shade)

    def _level(self, game: Game) -> None:
        t = game.tick
        self.frame.blit(self.back, (0, 0))
        self._backdrop_lights(self.scene, t)
        for img, pos in self.play:
            self.frame.blit(img, pos)

        bx, by = self.level.blossom
        won = game.mode is Mode.WON
        popped = won and game.mode_tick >= POP  # the bubble has burst; it doesn't come back
        if not popped:
            self._put_c(self.s.orb[0], bx, by - 1)
        self._put(self.s.blossom, bx - 6, by - 6)
        glint = (t // 14) % 40
        if not won and glint < 8:  # an idle glint now and then
            self._put(self.s.sparks["p"][glint], bx + 7, by - 12)
        if won:
            self._absorb(game)

        if game.ghost is not None and game.mode in (Mode.BUILD, Mode.PLAY):
            self._ghost(game)

        run = game.run
        for i, n in enumerate(game.placed):
            if run is not None and run.notes[i].peeled:
                continue
            left = max(0, game.press.get(i, 0) - t)
            self._note(n, dip=2.0 * math.sin(math.pi * left / PRESS_TICKS) if left else 0.0)
        for p in game.peels:
            self._peel(p, t)
        self._trail(game)

        egg_out = game.mode is Mode.PLAY  # once won, `_absorb` draws the egg
        behind = game.mode is Mode.PLAY and game.mode_tick < EGG_BEHIND_TICKS
        if egg_out and behind:
            self._egg(game)
        self._lori(game)
        nx, ny = self.level.nest
        nest = self.s.nest
        self._put(nest, nx - nest.get_width() // 2, ny + NEST_FOOT - nest.get_height())
        if egg_out and not behind:
            self._egg(game)
        if game.mode is Mode.POOF and game.splat is not None:
            self._splat(game.splat, t)
        for burst in game.bursts:
            self._burst(burst, t)
        if won:
            self._sparks(game.mode_tick)
            if game.mode_tick > CELEBRATE:  # party once the nectar has taken the egg
                self._confetti(game.mode_tick - CELEBRATE)

        self._lights(game)
        if won:  # after the light pass, so the glow behind it never washes out its colours
            self._chick(game.mode_tick - POP - HATCH)
        self._finish()

        self._hud(game)
        if game.held is not None:
            self._note(game.held, screen=game.pointer)
        if won and game.mode_tick > CELEBRATE:
            self._centered("nectar!", 50, spacing=2)
            self._centered("space · again", 62, colour=pal.MUTED)
        elif game.mode is Mode.POOF:
            self._centered("splat!" if game.result is Outcome.SPLAT else "oops!", 50, spacing=2)

    # -- passes -----------------------------------------------------------------------------

    def _backdrop_lights(self, scene: Night, tick: int) -> None:
        """The backdrop's lights as soft bokeh: stars swell and fade, party windows drift
        between colours, and a slow wave rolls along the string lights."""
        for x, y, phase in scene.twinkles:
            period = 300 + phase % 300  # 2.5 to 5 s per star
            v = _wave(tick, period, phase) ** 3  # mostly faint, now and then bright
            if v > 0.06:
                self._add(self.star_bokeh[_level(v)], x + 0.5, y + 0.5)
        for x, y, i in scene.windows:
            w = tick / WINDOW_FADE + i * 0.37
            colour = (int(w) + i) % len(pal.PARTY)
            v = math.sin(math.pi * (w % 1.0))  # dark at the moment the colour changes
            self._add(self.window_bokeh[colour][_level(v)], x + 0.5, y + 0.5)
        for i, (x, y) in enumerate(scene.bulbs):
            colour = i % len(pal.PARTY)
            v = 0.15 + 0.85 * _wave(tick, BULB_WAVE, -i * 0.55)
            self._add(self.bulb_halo[colour][_level(v)], x + 0.5, y + 1)
            self._add(self.bulb_bokeh[colour][_level(v)], x + 0.5, y + 1)

    def _lights(self, game: Game) -> None:
        """Soft glows on the playfield: mushrooms, the blossom, the egg, bounce flashes."""
        t = game.tick
        for j, (x, y) in enumerate(self.scene.lamps):
            self._add(self.glow_lamp[_level(_wave(t, 540, j * 1.7))], x + 0.5, y)
        bx, by = self.level.blossom
        if not (game.mode is Mode.WON and game.mode_tick >= POP):  # no bubble, no bubble glow
            self._add(self.glow_orb[_level(_wave(t, GLOW_BREATH))], bx, by - 1)
        if game.mode is Mode.WON:
            self._absorb_lights(game)
        elif game.mode is Mode.PLAY and game.mode_tick >= EGG_BEHIND_TICKS:
            self._add(self.glow_egg, *game.egg_pos)
        for burst in game.bursts:
            age = t - burst.born
            if burst.kind == "ring" and age < FLASH_TICKS:
                fade = (1 - age / FLASH_TICKS) ** 2  # flares, then eases away
                self._add(self.glow_flash[_level(fade)], burst.x, burst.y)

    def _finish(self) -> None:
        self.frame.blit(self.vignette, (0, 0), special_flags=pygame.BLEND_MULT)

    # -- pieces -----------------------------------------------------------------------------

    def _idle(self, tick: int) -> int:
        return IDLE_CYCLE[(tick * 7 // TICKS_PER_SECOND) % 8]

    def _lori(self, game: Game) -> None:
        """Lori stays in her nest: idles, squash-hops as she pops the egg out, cheers a win."""
        frame, hop = self._idle(game.tick), 0.0
        t = game.mode_tick
        if game.mode is Mode.PLAY and t < POP_TICKS:
            if t < 8:
                frame = SQUASH_HARD  # wind up
            elif t < 24:
                frame, hop = 0, 4 * math.sin(math.pi * (t - 8) / 16)  # pop!
            else:
                frame = SQUASH_SOFT  # land back in the nest
        elif game.mode is Mode.WON:
            frame = BLINK if (t // 30) % 3 == 2 else 0
            hop = 3 * abs(math.sin(math.pi * t / 40))
        elif game.mode is Mode.POOF and t < 40:
            frame = BLINK
        nx, ny = self.level.nest
        ax, ay = LORI_ANCHOR
        self._put(self.s.lori[frame], nx - ax, ny - ay - hop)

    def _egg(self, game: Game) -> None:
        ex, ey = game.egg_pos
        self._put_c(self.s.halo[(game.tick // 60) % 2], ex, ey)
        half = EGG_BOX / 2
        self._put(self.s.egg[game.egg_frame], ex - half, ey - half)

    def _egg_pose(self, game: Game) -> tuple[float, float, float, float, bool] | None:
        """Where the won egg is and how it's squashed: (x, y, x-scale, y-scale, white).

        Lift, then a quadratic arc into the orb's centre that speeds up as it goes (Sprite
        Fusion's pickup timing), a slow shrink while the shield closes, two white blinks, then
        squash, white stretch, and gone. None means not drawn this tick.
        """
        m = game.mode_tick
        x0, y0 = game.egg_pos
        tx, ty = self.level.blossom[0], self.level.blossom[1] - 1
        if m < LIFT:
            lift = _out_cubic(m / LIFT)
            return x0, y0 - 4 * lift, 1 - 0.15 * lift, 1 + 0.2 * lift, False
        if m < ARRIVE:
            u = ((m - LIFT) / FLY) ** 2.2
            sx, sy = x0, y0 - 4
            mx, my = (sx + tx) / 2, min(sy, ty) - max(8.0, math.hypot(tx - sx, ty - sy) * 0.35)
            x = (1 - u) ** 2 * sx + 2 * (1 - u) * u * mx + u * u * tx
            y = (1 - u) ** 2 * sy + 2 * (1 - u) * u * my + u * u * ty
            return x, y, 1 - 0.15 * u, 1 - 0.15 * u, False
        if m < POP:
            if m >= POP - 16 and ((POP - m) // 4) % 2 == 1:
                return None  # blinking out: white, gone, white, gone
            shrink = 0.85 - 0.35 * _smooth(CONTRACT, POP, m)
            return tx, ty, shrink, shrink, m >= POP - 16
        if m < POP + 3:
            return tx, ty, 0.75, 0.3, False  # squash...
        if m < POP + 6:
            return tx, ty, 0.35, 0.72, True  # ...white stretch...
        return None  # ...and out: the chick takes its place

    def _absorb(self, game: Game) -> None:
        """The nectar takes the egg: glide in, hex shield, pop, white flash, four-point sparkle."""
        m = game.mode_tick
        k, f = self.k, self.frame
        bx, cy = self.level.blossom[0], self.level.blossom[1] - 1
        centre = (round(bx * k), round(cy * k))
        game_frame = self.s.egg[game.egg_frame]

        if LIFT <= m < ARRIVE:  # a short streak behind the flying egg
            pts = []
            for back in range(0, 7):
                pose = self._pose_at(game, m - back)
                if pose is not None and m - back >= LIFT:
                    pts.append((round(pose[0] * k), round(pose[1] * k)))
            if len(pts) > 1:
                pygame.draw.lines(f, pal.MAGIC[2], False, pts, k)
                pygame.draw.lines(f, pal.MAGIC[3], False, pts[:3], max(1, k // 2))

        pose = self._egg_pose(game)
        if pose is not None:
            x, y, sx, sy, white = pose
            w, h = game_frame.get_size()
            img = game_frame
            if white:
                img = pygame.mask.from_surface(game_frame).to_surface(
                    setcolor=pal.WHITE_HOT, unsetcolor=(0, 0, 0, 0)
                )
            size = (max(k, round(w * sx * k)), max(k, round(h * sy * k)))
            self._blit_c(pygame.transform.scale(img, size), x, y)

        if ARRIVE <= m < POP + 12:  # the shield forms around it inside the ring, then closes
            radius = SHIELD_R * (1 - 0.5 * _smooth(CONTRACT, POP, m))
            t = (m - ARRIVE) / TICKS_PER_SECOND
            shield = fx.hex_shield(radius, t, gone=(POP - ARRIVE) / TICKS_PER_SECOND)
            self._blit_c(pygame.transform.scale_by(shield, k), bx, cy)

        a = m - POP
        if 0 <= a < 10:  # white-hot disc collapsing to a point
            pygame.draw.circle(f, pal.WHITE_HOT, centre, round((5 * (1 - a / 10) + 1) * k))
        if 0 <= a < 48:  # a ring eases out and cools
            u = a / 48
            colour = pal.WHITE_HOT if u < 0.3 else pal.MAGIC[3] if u < 0.6 else pal.MAGIC[2]
            width = max(1, round(2 * (1 - u) * k))
            pygame.draw.circle(f, colour, centre, round((2 + 20 * _out_cubic(u)) * k), width)
        if 0 <= a < SHATTER:
            self._shatter(a, bx, cy)

        s = a / TICKS_PER_SECOND
        for i, (angle, speed, tone) in enumerate(self.petals):  # petals drift down, turning
            if not 0 <= s <= 3.0:
                continue
            spread = (1 - math.exp(-3 * s)) / 3
            x = bx + speed * math.cos(angle) * spread + 4 * math.sin(2.4 * s + i)
            y = cy + speed * math.sin(angle) * spread + 16 * s * s / (1 + s)
            if y >= PAD_TOP:
                continue
            spin = abs(math.cos(2.2 * s + i * 0.9))
            w = max(1, round(2 * k * spin))
            colour = (pal.EMBER.light, pal.EMBER.base)[tone]
            f.fill(colour, (round(x * k) - w // 2, round(y * k), w, k))

    def _shatter(self, a: int, bx: float, cy: float) -> None:
        """The bubble bursts: its ring breaks into arcs that fly out, turn and shrink away,
        and the glow dots that filled it scatter. `a` is ticks since the pop."""
        u = a / SHATTER
        spread = _out_cubic(u)
        tone = pal.MAGIC[3] if u < 0.25 else pal.MAGIC[2] if u < 0.6 else pal.MAGIC[1]
        for start, span, turn in self.shards:
            radius = 11 + 24 * spread
            length = span * (1 - 0.8 * u)  # each arc shortens as it flies
            first = start + turn * spread
            steps = max(1, round(length * radius))  # about one art pixel apart
            for i in range(steps + 1):
                ang = first + length * i / steps
                self._dot(bx + radius * math.cos(ang), cy + radius * math.sin(ang), tone)
        s = a / TICKS_PER_SECOND
        for ang, r0, speed in self.motes_in:
            if u > 0.7 and (round(r0 * 10) + a) % 3 == 0:
                continue  # thinning out at the end, a dither-like fade
            d = r0 + speed * (1 - math.exp(-4 * s)) / 4
            colour = pal.MAGIC[1] if u < 0.5 else pal.MAGIC[0]
            self._dot(bx + d * math.cos(ang), cy + d * math.sin(ang) + 10 * s * s, colour)

    def _ghost(self, game: Game) -> None:
        """Last run's path as a dotted rainbow: in build mode it draws itself on from the nest,
        bounces get a little star and the end a marker; while the next run plays it stays
        faint underneath. A soft light runs along it, nest to end, so it reads as a direction."""
        ghost = game.ghost
        assert ghost is not None
        dots = _resample(ghost.points, 4.5)
        building = game.mode is Mode.BUILD
        shown = len(dots) if not building else int(len(dots) * min(1.0, game.mode_tick / 90))
        ramps = list(pal.RAMPS.values())
        head = game.tick // 9
        for i, (x, y) in enumerate(dots[:shown]):
            ramp = ramps[(i // 3) % len(ramps)]
            if not building:
                colour = ramp.dark
            else:
                colour = ramp.light if (i - head) % 16 == 0 else ramp.base
            self._dot(x, y, colour)
        if not building or shown < len(dots):
            return
        breathe = 1 + round(_wave(game.tick, 240))  # 1 or 2: a slow twinkle
        for x, y in ghost.springs:
            self._star(x, y + 4, breathe, pal.SUN.light)
        ex = min(max(ghost.end[0], 4.0), BOARD_W - 4.0)
        ey = min(max(ghost.end[1], 4.0), PAD_TOP - 2.0)
        if ghost.outcome is Outcome.WON:
            self._star(ex, ey, 2, pal.SUN.light)
        else:  # a small x where the attempt ended
            for d in (-1, 0, 1):
                self._dot(ex + d, ey + d, pal.EMBER.base)
                self._dot(ex + d, ey - d, pal.EMBER.base)

    def _chick(self, c: int) -> None:
        """The chick, `c` ticks after it appears: bursts out stretched tall and white, squashes
        wide, settles, then floats in the nectar, flapping excitedly, later blinking now and
        then."""
        if c < 0:
            return
        bx, cy = self.level.blossom[0], self.level.blossom[1] - 1
        if c < 6:
            u = c / 6
            sx, sy = 0.5 + 0.3 * u, 0.5 + 0.85 * u
        elif c < 12:
            u = (c - 6) / 6
            sx, sy = 0.8 + 0.5 * u, 1.35 - 0.6 * u
        elif c < 22:
            u = _out_cubic((c - 12) / 10)
            sx, sy = 1.3 - 0.3 * u, 0.75 + 0.25 * u
        else:
            sx = sy = 1.0
        if c < 22:
            frame = 2  # wings out as it bursts free
        elif c < 140:
            frame = 2 if (c // 10) % 2 else 0  # excited little flaps
        else:
            frame = 1 if (c % 260) < 10 else 0  # calm now; a blink every couple of seconds
        img = self.s.chick[frame]
        if c < 3:  # still white-hot from the pop
            img = pygame.mask.from_surface(img).to_surface(
                setcolor=pal.WHITE_HOT, unsetcolor=(0, 0, 0, 0)
            )
        bob = 0.8 * math.sin(2 * math.pi * c / 150) if c >= 22 else 0.0
        k = self.k
        w, h = img.get_size()
        size = (max(k, round(w * sx * k)), max(k, round(h * sy * k)))
        # Scale about the chick's feet, so the squash reads as a little landing.
        self._blit_c(pygame.transform.scale(img, size), bx, cy + 1 + h / 2 * (1 - sy) + bob)

    def _pose_at(self, game: Game, tick: int) -> tuple[float, float, float, float, bool] | None:
        """`_egg_pose` as it was at an earlier mode tick (for the flight streak)."""
        saved = game.mode_tick
        game.mode_tick = max(0, tick)
        try:
            return self._egg_pose(game)
        finally:
            game.mode_tick = saved

    def _sparks(self, m: int) -> None:
        """After the pop: sparks burst out, curve home into the blossom, leave rising motes."""
        a = m - POP
        if a < 0:
            return
        bx, cy = self.level.blossom[0], self.level.blossom[1] - 1
        plan = self.spark_plan
        for path in plan.paths:
            point = path[a] if a < len(path) else None
            if point is None:
                continue
            for back in range(1, 5):  # a dotted tail
                prev = path[a - back] if a - back >= 0 else None
                if prev is not None:
                    colour = pal.MAGIC[3] if back < 3 else pal.MAGIC[2]
                    self._dot(bx + prev[0], cy + prev[1], colour)
            x, y, left, size, tone = point
            self._star(bx + x, cy + y, round(size * min(1.0, left * 3)), SPARK_TONES[tone])
        for tick in plan.rings:  # each third spark home pops a small ring
            age = a - tick
            if 0 <= age < 48:
                u = age / 48
                colour = pal.WHITE_HOT if u < 0.3 else pal.MAGIC[3]
                r = round((2 + 12 * _out_cubic(u)) * self.k)
                width = max(1, round(2 * (1 - u) * self.k))
                pygame.draw.circle(
                    self.frame, colour, (round(bx * self.k), round(cy * self.k)), r, width
                )
        for born, x0, y0, vx, vy, life, tone, size in plan.motes:  # motes rise and twinkle out
            age = (a - born) / TICKS_PER_SECOND
            if not 0 <= age < life:
                continue
            left = 1 - age / life
            if left * (0.6 + 0.4 * math.sin(age * 30)) <= 0.25:
                continue
            x = bx + x0 + vx * (1 - math.exp(-1.5 * age)) / 1.5
            y = cy + y0 + vy * age
            self._star(x, y, size, (pal.MAGIC[3], pal.SUN.light)[tone])

    def _absorb_lights(self, game: Game) -> None:
        m = game.mode_tick
        bx, cy = self.level.blossom[0], self.level.blossom[1] - 1
        pose = self._egg_pose(game)
        if pose is not None:  # the egg glows brighter as the nectar takes it
            v = 0.4 + 0.6 * min(1.0, m / ARRIVE)
            self._add(self.glow_flash[_level(v)], pose[0], pose[1])
        if m >= POP:
            v = math.exp(-(m - POP) / 30)
            if v > 0.02:
                self._add(self.glow_burst[_level(v)], bx, cy)
            if m >= POP + HATCH:  # a warm glow stays with the new chick
                self._add(self.glow_flash[_level(0.35)], bx, cy)
        a = m - POP
        for path in self.spark_plan.paths:
            point = path[a] if 0 <= a < len(path) else None
            if point is not None:
                x, y, left, _, _ = point
                self._add(self.glow_spark[_level(min(1.0, left * 2))], bx + x, cy + y)

    def _star(self, x: float, y: float, arm: int, colour: pal.RGB) -> None:
        """A four-point sparkle: a white core, `arm` pixels each way, darker tips (and
        diagonal tips once it's big), in chunky pixels at a smooth position."""
        self._dot(x, y, pal.WHITE_HOT if arm > 0 else colour)
        tip = _mix(colour, pal.MAGIC[1], 0.4)
        for d in range(1, arm + 1):
            c = tip if d == arm and arm > 1 else colour
            for dx, dy in ((d, 0), (-d, 0), (0, d), (0, -d)):
                self._dot(x + dx, y + dy, c)
        if arm >= 3:
            for dx, dy in ((1, 1), (-1, 1), (1, -1), (-1, -1)):
                self._dot(x + dx, y + dy, tip)

    def _dot(self, x: float, y: float, colour: pal.RGB) -> None:
        """One art pixel, k x k, centred on board point (x, y)."""
        k = self.k
        self.frame.fill(colour, (round(x * k) - k // 2, round(y * k) - k // 2, k, k))

    def _splat(self, splat: Splat, tick: int) -> None:
        """The egg on the floor: squash, crack, puddle; shell bits and yolk drops arc away."""
        age = tick - splat.born
        frame = self.s.splat[0 if age < 5 else 1 if age < 14 else 2]
        w, h = frame.get_size()
        self._put(frame, splat.x - w / 2, splat.y - h + 1)
        t = age / TICKS_PER_SECOND
        for i, shard in enumerate(self.s.shards):
            vx, vy = SHARD_FLIGHTS[i]
            self._put(shard, *_arc(splat.x, splat.y - 4, vx, vy, t, splat.y - shard.get_height()))
        k = self.k
        for i, (vx, vy) in enumerate(YOLK_FLIGHTS):
            x, y = _arc(splat.x, splat.y - 3, vx, vy, t, splat.y - 1)
            colour = pal.SUN.base if i % 2 else pal.CREAM
            self.frame.fill(colour, (round(x * k), round(y * k), k, k))

    def _trail(self, game: Game) -> None:
        for x, y, born in game.trail:
            age = game.tick - born
            frame = 3 if age < 12 else 4 if age < 27 else 5 if age < TRAIL_LIFE else 0
            colour = "p" if (born // 6) % 2 else "b"
            self._put(self.s.sparks[colour][frame], x - 2, y - 2)

    def _note(
        self,
        n: PlacedNote,
        dip: float = 0.0,
        screen: tuple[int, int] | None = None,
    ) -> None:
        img = self._notes.get(n.angle)
        if img is None:
            img = self._notes[n.angle] = pygame.transform.rotate(self.big(self.s.note), -n.angle)
        if screen is not None:
            self.frame.blit(img, img.get_rect(center=screen))
            return
        up = n.up_normal()
        self._blit_c(img, n.x - up.x * dip, n.y - up.y * dip)

    def _peel(self, p: Peel, tick: int) -> None:
        """Paper flutters: a little lift, then a slow sway down, rocking smoothly as it goes."""
        t = (tick - p.born) / TICKS_PER_SECOND
        x = p.x0 + p.side * 20 * t + 5 * math.sin(5 * t)
        y = p.y0 + 30 * t - 10 * (1 - math.exp(-5 * t))
        angle = p.note.angle + p.side * 40 * math.sin(4 * t)
        self._blit_c(pygame.transform.rotate(self.big(self.s.note), -angle), x, y)

    def _burst(self, burst: Burst, tick: int) -> None:
        age = tick - burst.born
        if burst.kind == "ring":
            i = age // 6
            if i < len(self.s.rings):
                self._put_c(self.s.rings[i], burst.x, burst.y)
        elif burst.kind == "smoke":
            for k, (dx, dy) in enumerate(SMOKE_OFFSETS):
                i = age // 10 - k
                if 0 <= i < len(self.s.smoke):
                    self._put_c(self.s.smoke[i], burst.x + dx, burst.y + dy - age / 12)
        else:
            for k, (dx, dy) in enumerate(BURST_OFFSETS[: 2 * len(burst.colors)]):
                step = age // 6 - k
                if 0 <= step < 8:
                    colour = burst.colors[k % len(burst.colors)]
                    self._put(self.s.sparks[colour][step], burst.x + dx - 2, burst.y + dy - 2)

    def _confetti(self, tick: int) -> None:
        """Party confetti across the sky: paper bits that drift down, sway and turn slowly."""
        t = tick / TICKS_PER_SECOND
        k = self.k
        for i in range(56):
            x = (i * 53 + 11) % BOARD_W + 6 * math.sin(2.2 * t + i * 0.7)
            y = -6 - (i * 17) % 70 + (24 + (i * 7) % 18) * t
            if not 0 <= y < PAD_TOP:
                continue
            spin = abs(math.cos(2.6 * t + i))  # the paper turns edge-on and back
            w = max(1, round(2 * k * spin))
            self.frame.fill(pal.PARTY[i % 4], (round(x * k) - w // 2, round(y * k), w, k))

    def _hud(self, game: Game) -> None:
        self._put(self._text(f"1-1 {self.level.name}"), 6, 6)
        if game.mode is Mode.BUILD:
            hint = self._text("q e rotate · r reset", pal.MUTED)
            self._put(hint, BOARD_W - hint.get_width() - 6, 6)
            for _, rect in game.pad_slots():
                self._put(self.s.note, *rect.topleft)
            drop = self._text("space · drop")
            r = drop.get_rect(center=DROP_BUTTON.center)
            self._put(drop, r.x, r.y)

    def _sparkles(
        self, tick: int, sparks: list[tuple[int, int, str, int]], speed: int = 18
    ) -> None:
        """Each sparkle opens and closes over about a second, then rests for two."""
        for x, y, colour, phase in sparks:
            step = (tick // speed + phase) % 24
            if step < 8:
                self._put(self.s.sparks[colour][step], x - 2, y - 2)

    def _text(self, s: str, colour: pal.RGB = pal.CREAM, spacing: int = 1) -> pygame.Surface:
        """Pixel text with a 1 px ink drop shadow (board resolution; `_put` scales it)."""
        key = (s, colour, spacing)
        img = self._texts.get(key)
        if img is None:
            face = text(self.s.font, s, colour, spacing)
            shade = text(self.s.font, s, pal.INK, spacing)
            img = pygame.Surface((face.get_width() + 1, face.get_height() + 1), pygame.SRCALPHA)
            img.blit(shade, (1, 1))
            img.blit(face, (0, 0))
            self._texts[key] = img
        return img

    def _centered(self, s: str, y: int, spacing: int = 1, colour: pal.RGB = pal.CREAM) -> None:
        img = self._text(s, colour, spacing)
        self._put(img, (BOARD_W - img.get_width()) // 2, y)

    # -- placing at window resolution ---------------------------------------------------------

    def big(self, surf: pygame.Surface) -> pygame.Surface:
        """`surf` with each pixel blown up to k x k: the same chunky art, ready to place."""
        img = self._big.get(id(surf))
        if img is None:
            img = self._big[id(surf)] = pygame.transform.scale_by(surf, self.k)
        return img

    def _put(self, surf: pygame.Surface, x: float, y: float) -> None:
        """Blit a board-resolution sprite with its top left at board point (x, y), sub-pixel."""
        self.frame.blit(self.big(surf), (round(x * self.k), round(y * self.k)))

    def _put_c(self, surf: pygame.Surface, x: float, y: float) -> None:
        """Blit a board-resolution sprite centred on board point (x, y), sub-pixel."""
        self._blit_c(self.big(surf), x, y)

    def _blit_c(self, img: pygame.Surface, x: float, y: float) -> None:
        """Blit an already-scaled image centred on board point (x, y)."""
        cx, cy = round(x * self.k), round(y * self.k)
        self.frame.blit(img, (cx - img.get_width() // 2, cy - img.get_height() // 2))

    def _add(self, glow: pygame.Surface, x: float, y: float) -> None:
        """Lay a soft glow, centred on board point (x, y), with additive blending."""
        cx, cy = round(x * self.k), round(y * self.k)
        pos = (cx - glow.get_width() // 2, cy - glow.get_height() // 2)
        self.frame.blit(glow, pos, special_flags=pygame.BLEND_ADD)


SHARD_FLIGHTS = [(-62, -95), (-34, -130), (-8, -75), (28, -120), (58, -88)]  # px/s
YOLK_FLIGHTS = [(-44, -60), (-18, -84), (20, -78), (46, -56)]
SPLAT_GRAVITY = 360.0


def _arc(x0: float, y0: float, vx: float, vy: float, t: float, floor: float) -> tuple[float, float]:
    """A thrown bit's position after `t` s, coming to rest where it meets `floor`."""
    y = y0 + vy * t + 0.5 * SPLAT_GRAVITY * t * t
    if y < floor:
        return x0 + vx * t, y
    land = (-vy + math.sqrt(vy * vy + 2 * SPLAT_GRAVITY * (floor - y0))) / SPLAT_GRAVITY
    return x0 + vx * land, floor


def _resample(points: list[tuple[float, float]], gap: float) -> list[tuple[float, float]]:
    """Points every `gap` px along a polyline, so dots space evenly whatever the egg's speed."""
    if not points:
        return []
    out = [points[0]]
    carry = 0.0
    for (x0, y0), (x1, y1) in pairwise(points):
        seg = math.hypot(x1 - x0, y1 - y0)
        d = gap - carry
        while d <= seg:
            f = d / seg
            out.append((x0 + (x1 - x0) * f, y0 + (y1 - y0) * f))
            d += gap
        carry = seg - (d - gap)
    return out


def _out_cubic(t: float) -> float:
    t = min(1.0, max(0.0, t))
    return 1 - (1 - t) ** 3


def _smooth(a: float, b: float, x: float) -> float:
    """0 before `a`, 1 after `b`, an S-curve between."""
    if x <= a:
        return 0.0
    if x >= b:
        return 1.0
    t = (x - a) / (b - a)
    return t * t * (3 - 2 * t)


def _mix(a: pal.RGB, b: pal.RGB, t: float) -> pal.RGB:
    """`a` at t=0 to `b` at t=1."""
    return (
        round(a[0] + (b[0] - a[0]) * t),
        round(a[1] + (b[1] - a[1]) * t),
        round(a[2] + (b[2] - a[2]) * t),
    )


def _near_nest(x: int, y: int, level: Level) -> bool:
    nx, ny = level.nest
    return abs(x - nx) < 22 and abs(y - (ny + NEST_FOOT)) < 4
