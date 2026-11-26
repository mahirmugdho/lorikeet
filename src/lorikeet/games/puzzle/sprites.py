"""Sprites: the art kit's PNGs, plus hand-placed char maps for the new pieces.

New sprites follow the kit's `hand.py` approach: a grid of characters, a few palette colours,
and an automatic dark-violet outline. Needs an initialised pygame display (`convert_alpha`).
"""

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pygame

from . import fx
from . import palette as pal
from .dither import dither_levels

ASSETS = Path(__file__).parent / "assets"
FONT_PATH = ASSETS / "Silkscreen-Regular.ttf"
FRAME = 24  # Lori's sheet: 8 frames of 24 x 24

# Lori's frames, in sheet order: normal, normal, squash, squash, normal, normal, blink, normal.
IDLE_CYCLE = tuple(range(8))
SQUASH_SOFT, SQUASH_HARD, BLINK = 2, 3, 6

# -- new sprites (show at x10 before use: `python -m lorikeet.games.puzzle --sprites out.png`) --

NEST_KEY = {"a": pal.SUN.base, "b": pal.TWIG[0], "c": pal.TWIG[1], "d": pal.INK}
NEST = [  # a woven bowl: straw rim, twigs darkening into shadow, curved underside
    "b.............................b",
    ".aabbaabbaabbaabbaabbaabbaabba.",
    ".bbccbbaabbccbbaabbccbbaabbccb.",
    "..cbbccbbccbbccbbccbbccbbccbc..",
    "...ccddccbbccddccbbccddccbbc...",
    "....ddccddddccddddccddddccd....",
    "......ddddddddddddddddddd......",
]

BLOSSOM_KEY = {
    "l": pal.EMBER.light,
    "b": pal.EMBER.base,
    "d": pal.EMBER.dark,
    "y": pal.SUN.base,
    "C": pal.SUN.light,
    "c": pal.CREAM,
    "g": pal.LEAF.base,
    "G": pal.LEAF.dark,
}
BLOSSOM = [
    "...lllll...",
    "..lbbbbbd..",
    ".lbbbybbbd.",
    ".lbbyCybbd.",
    "lbbyCcCybbd",
    "lbbbyCybbbd",
    ".dbbbybbbd.",
    ".ddbbbbbdd.",
    "..dddddd...",
    ".....G.....",
    "...gGG.....",
    ".....G.....",
]


def charmap(rows: list[str], key: dict[str, pal.RGB], outline: bool = True) -> pygame.Surface:
    """Turn a char map into a sprite. `.` is clear; `outline` rings the shape in INK."""
    w, h = len(rows[0]), len(rows)
    assert all(len(r) == w for r in rows), [len(r) for r in rows]
    pad = 1 if outline else 0
    surf = pygame.Surface((w + 2 * pad, h + 2 * pad), pygame.SRCALPHA)
    filled = [[ch != "." for ch in r] for r in rows]
    for y, r in enumerate(rows):
        for x, ch in enumerate(r):
            if ch != ".":
                surf.set_at((x + pad, y + pad), key[ch])
    if outline:
        for y in range(-1, h + 1):
            for x in range(-1, w + 1):
                inside = 0 <= x < w and 0 <= y < h and filled[y][x]
                if inside:
                    continue
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < w and 0 <= ny < h and filled[ny][nx]:
                        surf.set_at((x + pad, y + pad), pal.INK)
                        break
    return surf


def ledge(w: int, h: int) -> pygame.Surface:
    """A stone-tile shelf: a lit top edge, a course of tiles, seams, and glowing mushrooms."""
    xs = np.arange(w)
    rgb = np.empty((h, w, 3), dtype=np.uint8)
    rgb[:, :] = pal.STONE[2]
    rgb[0, :] = pal.STONE[0]
    rgb[1:4, :] = pal.STONE[1]
    rgb[4, :] = pal.STONE[3]  # seam under the top course
    rgb[1:4, (xs % 16) == 7] = pal.STONE[3]  # top-course joints
    rgb[5:, (xs % 16) == 15] = pal.STONE[3]  # lower joints, offset like brickwork
    if h > 8:
        rgb[h - 3, (xs * 5 + 2) % 9 == 0] = pal.STONE[3]  # a little wear
    rgb[:, 0] = rgb[:, -1] = pal.INK
    rgb[-1, :] = pal.INK
    return pygame.surfarray.make_surface(rgb.swapaxes(0, 1)).convert()


MUSHROOM = ["ccc", "cCc", ".s."]  # a glowing cap on a pale stem; sits on a shelf
MUSHROOM_KEY = {"c": pal.PARTY[2], "C": pal.WHITE_HOT, "s": pal.CREAM}


# -- the chick ---------------------------------------------------------------------------------
# What hatches from the nectar: a fluffy round baby lorikeet in Lori's own plumage colours (the
# kit's hand.py palette), big eye, tiny beak. Three frames: normal, blink, wings up.

CHICK_KEY = {
    "c": (150, 190, 255),
    "w": (215, 232, 255),
    "b": (82, 128, 245),
    "B": (44, 72, 190),
    "E": (18, 12, 36),
    "W": (255, 255, 255),
    "k": (255, 140, 60),
    "K": (190, 80, 35),
    "P": (255, 140, 170),
    "y": (255, 214, 90),
    "s": (255, 150, 115),
    "r": (245, 95, 70),
    "R": (185, 50, 55),
    "h": (130, 235, 165),
    "g": (60, 190, 115),
    "G": (25, 120, 80),
    "v": (150, 115, 240),
    "V": (95, 65, 180),
    "F": (240, 130, 70),
}
CHICK = [
    "....ccb.....",
    "...cwcbb....",
    "..ccwbbbbb..",
    ".ccbbbbEWbk.",
    ".cbbbbbEEbkk",
    ".gbbbbbbPbK.",
    "hggBBbyyyyy.",
    "hgggGysssrr.",
    ".ggGyssrrrR.",
    "..GvvrrrrR..",
    "...vvvVVV...",
    "....F...F...",
]
CHICK_BLINK = [*CHICK[:3], ".ccbbbbbbbk.", ".cbbbbbEEbkk", *CHICK[5:]]
CHICK_FLAP = [
    *CHICK[:4],
    "hcbbbbbEEbkk",
    "hgbbbbbbPbK.",
    ".hgBBbyyyyy.",
    "..ggGysssrr.",
    *CHICK[8:],
]


def chick_frames() -> list[pygame.Surface]:
    return [charmap(rows, CHICK_KEY) for rows in (CHICK, CHICK_BLINK, CHICK_FLAP)]


# -- the splat ----------------------------------------------------------------------------------
# Three frames on the floor: the egg squashes flat, cracks open, then settles as a puddle with a
# yolk. Rows are written centred and padded to SPLAT_W, so each one reads like a drawing.

SPLAT_W = 25
SPLAT_KEY = {
    "s": pal.EGG.base,
    "S": pal.EGG.dark,
    "k": pal.SKY.dark,
    "w": pal.CREAM,
    "W": pal.WHITE_HOT,
    "y": pal.SUN.base,
    "Y": pal.SUN.light,
    "o": pal.SUN.dark,
}
SPLAT_FRAMES = [
    [  # impact: the shell squashes flat
        "sssssss",
        "ssssksssssS",
        "ssksssssssSSS",
        "SssssssssksSSSS",
        "SSSSSSSSSSSSS",
    ],
    [  # crack: shell halves tip outward, white and yolk burst through
        "s...............S",
        "sS.....WwwwW.....Ss",
        "Ss....wwYYYyww....sS",
        "Ss...wwyyYYyyoww...SS",
        "SSSwwwwwyyyyowwwwwSSS",
    ],
    [  # settled: a wide puddle, the yolk sitting proud in the middle
        "WwwwW",
        "wwwYYyyww",
        "wwwwyYYyyoww",
        "Wwwwwwwyyyyowwwwww",
        "wwwwwwwwwwwwwwwwwwwwwww",
    ],
]
SHARD_KEY = {"s": pal.EGG.base, "S": pal.EGG.dark, "k": pal.SKY.dark}
SHARDS = [["sS", "S."], ["sk", "SS"], ["s", "S"], ["ss", ".S"], ["Sk"]]


def _centred(rows: list[str], width: int) -> list[str]:
    return [r.center(width, ".") for r in rows]


def splat_frames() -> list[pygame.Surface]:
    return [charmap(_centred(f, SPLAT_W), SPLAT_KEY) for f in SPLAT_FRAMES]


def shard_sprites() -> list[pygame.Surface]:
    return [charmap(sh, SHARD_KEY, outline=False) for sh in SHARDS]


# -- the egg ------------------------------------------------------------------------------------
# 32 frames of a full turn. The shell outline comes from an egg curve (pointy end up at frame 0)
# and the speckles are hand-placed in the egg's own coordinates, so they turn with it. Light
# stays fixed at the top left: the shading is worked out after turning, never rotated with it.

EGG_FRAMES = 32  # a full turn; with smooth movement this reads as a continuous roll
EGG_BOX = 15  # frame size; the shell is about 11 x 12 inside it
# Each speckle is a 2-pixel blot (its point and the one beside it, in egg space), so the turn
# reads even when the egg is moving fast.
EGG_SPECKLES = ((-2.4, -2.2), (1.6, -3.6), (2.2, 0.2), (-1.0, 2.0), (1.8, 3.4), (-3.4, 0.8))


def _in_egg(x: float, y: float) -> bool:
    """Egg space, y down: wider toward +y, pointy toward -y."""
    a, b, k = 5.3, 5.9, 0.16
    w = a * (1 + k * y / b)
    return (x / w) ** 2 + (y / b) ** 2 <= 1.0


def egg_frame(angle: float) -> pygame.Surface:
    """The egg turned `angle` radians clockwise on screen."""
    n, c = EGG_BOX, EGG_BOX / 2
    ca, sa = np.cos(angle), np.sin(angle)
    filled = np.zeros((n, n), dtype=bool)
    light = np.zeros((n, n), dtype=np.float64)
    for py in range(n):
        for px in range(n):
            dx, dy = px + 0.5 - c, py + 0.5 - c
            if _in_egg(dx * ca + dy * sa, -dx * sa + dy * ca):
                filled[py, px] = True
                light[py, px] = 0.75 + (dx + dy) / 7.0  # 0 lit (top left) .. 2 shade
    tones = dither_levels(np.clip(light, 0.0, 2.0), 3)
    surf = pygame.Surface((n, n), pygame.SRCALPHA)
    shell = (pal.EGG.light, pal.EGG.base, pal.EGG.dark)
    for py in range(n):
        for px in range(n):
            if filled[py, px]:
                surf.set_at((px, py), shell[tones[py, px]])
    for k, (sx, sy) in enumerate(EGG_SPECKLES):
        colour = (pal.SKY.dark, pal.DUSK.dark)[k % 2]
        for ox in (0.0, 1.0):
            ex, ey = sx + ox, sy
            px, py = int(c + ex * ca - ey * sa), int(c + ex * sa + ey * ca)
            if 0 <= px < n and 0 <= py < n and filled[py, px]:
                surf.set_at((px, py), colour)
    # A fixed glint where the light hits, whichever way the egg faces.
    glint = (int(c - 2.5), int(c - 3.0))
    if filled[glint[1], glint[0]]:
        surf.set_at(glint, pal.WHITE_HOT)
    for py in range(n):
        for px in range(n):
            if filled[py, px]:
                continue
            near = ((px + dx, py + dy) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))
            if any(0 <= x < n and 0 <= y < n and filled[y, x] for x, y in near):
                surf.set_at((px, py), pal.INK)
    return surf


def egg_frames() -> list[pygame.Surface]:
    return [egg_frame(2 * np.pi * i / EGG_FRAMES) for i in range(EGG_FRAMES)]


def tones_surface(levels: np.ndarray, tones: tuple[pal.RGB, ...]) -> pygame.Surface:
    rgb = np.array(tones, dtype=np.uint8)[levels]
    return pygame.surfarray.make_surface(rgb.swapaxes(0, 1)).convert()


@dataclass
class Sprites:
    lori: list[pygame.Surface]
    note: pygame.Surface
    wordmark: pygame.Surface
    sparks: dict[str, list[pygame.Surface]]  # "y" | "b" | "v" -> 8 frames of 5 x 5
    nest: pygame.Surface
    blossom: pygame.Surface
    egg: list[pygame.Surface]
    mushroom: pygame.Surface
    orb: list[pygame.Surface]  # the blossom's glow, two shimmer phases
    halo: list[pygame.Surface]  # behind the egg, two shimmer phases
    rings: list[pygame.Surface]
    smoke: list[pygame.Surface]
    splat: list[pygame.Surface]
    chick: list[pygame.Surface]  # normal, blink, wings up
    shards: list[pygame.Surface]
    font: pygame.font.Font

    @classmethod
    def load(cls) -> "Sprites":
        def png(name: str) -> pygame.Surface:
            return pygame.image.load(ASSETS / name).convert_alpha()

        sheet = png("lori_idle_fx.png")
        lori = [sheet.subsurface((i * FRAME, 0, FRAME, FRAME)).copy() for i in range(8)]
        sparks = {}
        for c in "ybv":
            strip = png(f"spark_{c}.png")
            sparks[c] = [strip.subsurface((i * 5, 0, 5, 5)).copy() for i in range(8)]
        # Pink sparkles for the magic: the kit's violet strip with its two tones swapped.
        to_pink = {(180, 140, 255): pal.MAGIC[2], (240, 230, 255): pal.MAGIC[3]}
        sparks["p"] = [fx.recolor(f, to_pink) for f in sparks["v"]]
        return cls(
            lori=lori,
            note=png("note.png"),
            wordmark=png("wordmark.png"),
            sparks=sparks,
            nest=charmap(NEST, NEST_KEY),
            blossom=charmap(BLOSSOM, BLOSSOM_KEY),
            egg=egg_frames(),
            mushroom=charmap(MUSHROOM, MUSHROOM_KEY, outline=False),
            orb=[fx.orb(11, 0), fx.orb(11, 2)],
            halo=[fx.halo(10, 0), fx.halo(10, 1)],
            rings=fx.ring_frames(),
            smoke=fx.smoke_frames(),
            splat=splat_frames(),
            chick=chick_frames(),
            shards=shard_sprites(),
            font=pygame.font.Font(FONT_PATH, 8),
        )


def text(font: pygame.font.Font, s: str, color: pal.RGB, spacing: int = 0) -> pygame.Surface:
    """Pixel text: no antialiasing, optional extra letter spacing, trimmed to the glyph rows."""
    glyphs = [font.render(ch, False, color) for ch in s]
    w = sum(g.get_width() for g in glyphs) + spacing * max(0, len(s) - 1)
    out = pygame.Surface((max(1, w), font.get_height()), pygame.SRCALPHA)
    x = 0
    for g in glyphs:
        out.blit(g, (x, 0))
        x += g.get_width() + spacing
    # Crop to the cap rows of "H" so every string shares one baseline.
    box = font.render("H", False, color).get_bounding_rect()
    return out.subsurface((0, box.y, out.get_width(), box.h)).copy()


def sprite_sheet(sprites: Sprites, scale: int = 10) -> pygame.Surface:
    """The new sprites side by side at x`scale`, labelled, for review before they ship."""
    turn = pygame.Surface((EGG_BOX * 4 + 3, EGG_BOX * 2 + 1), pygame.SRCALPHA)
    for i in range(8):
        turn.blit(sprites.egg[i * 4], ((i % 4) * (EGG_BOX + 1), (i // 4) * (EGG_BOX + 1)))
    items = [
        ("nest", sprites.nest),
        ("blossom", sprites.blossom),
        ("ledge", ledge(40, 12)),
        ("egg", turn),
        ("glow", sprites.orb[0]),
        ("splat", sprites.splat[1]),
        ("puddle", sprites.splat[2]),
        ("chick", sprites.chick[0]),
        ("blink", sprites.chick[1]),
        ("flap", sprites.chick[2]),
    ]
    labels = [text(sprites.font, name, pal.MUTED) for name, _ in items]
    cols = [max(s.get_width(), lab.get_width()) for (_, s), lab in zip(items, labels, strict=True)]
    gap = 6
    w = sum(cols) + gap * (len(items) + 1)
    h = max(s.get_height() for _, s in items) + 18
    board = pygame.Surface((w, h))
    board.fill(pal.NIGHT[1])
    x = gap
    for (_, s), lab, col in zip(items, labels, cols, strict=True):
        board.blit(s, (x, 4))
        board.blit(lab, (x, h - 9))
        x += col + gap
    return pygame.transform.scale_by(board, scale)
