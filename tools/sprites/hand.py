# Lorikeet art kit: Lori's idle sheet. Verbatim from the kit except output paths (now ./out).
# Run: uv run --with pillow python tools/sprites/hand.py  (then word.py, then scene.py)
import os
import pathlib

OUT = pathlib.Path(__file__).parent / "out"
OUT.mkdir(exist_ok=True)
os.chdir(OUT)

from PIL import Image

# Lori, hand-placed. 24 x 23. Facing right, light from top-left.
BASE = [
    "............oo..........",  # 0  tuft
    "...........ocbo.........",  # 1
    ".........oooccbooo......",  # 2
    "........occcccbbbbo.....",  # 3
    ".......occwwccbbbbbo....",  # 4
    "......occwccbbbbEEbbo...",  # 5
    "......occccbbbbEWWEbkko.",  # 6
    "......occcbbbbbEWEEbjkko",  # 7
    "......occbbbbbbbEEPPkkKo",  # 8
    ".......oBbbbbbbbbbbYoKKo",  # 9
    "......ogBBbbbbYYyyyyyoo.",  # 10
    ".....oghgGBByyyyyyyyo...",  # 11
    "....ohhhggGYsssrrrrrRo..",  # 12
    "...ohhgggggGsssrrrrrRRo.",  # 13
    "...ohggggggGssrrrrrrRRo.",  # 14
    "...oggggggGGsrrrrrrRRRo.",  # 15
    "...ogGgGgGgGrrrrrrrRRRo.",  # 16
    "...oGoGoGoGvrrrrrRRRRo..",  # 17
    ".tTTo.o.o.ovvvvvvvVVo...",  # 18
    "tT........ovvvvvVVo.....",  # 19
    "...........ooooooo......",  # 20
    "............FF...FF.....",  # 21
    "...........F.F..F.F.....",  # 22
]

COL = {
    "o": (27, 20, 51),
    "c": (150, 190, 255),
    "w": (215, 232, 255),
    "b": (82, 128, 245),
    "B": (44, 72, 190),
    "E": (18, 12, 36),
    "W": (255, 255, 255),
    "k": (255, 140, 60),
    "j": (255, 190, 110),
    "K": (190, 80, 35),
    "P": (255, 140, 170),
    "Y": (230, 165, 40),
    "y": (255, 214, 90),
    "s": (255, 150, 115),
    "r": (245, 95, 70),
    "R": (185, 50, 55),
    "h": (130, 235, 165),
    "g": (60, 190, 115),
    "G": (25, 120, 80),
    "v": (150, 115, 240),
    "V": (95, 65, 180),
    "t": (102, 150, 255),
    "T": (44, 72, 190),
    "F": (240, 130, 70),
}

W, H = 24, 24  # one spare row of headroom at top for the bob


def grid(rows):
    g = [list(r.ljust(W, ".")) for r in rows]
    assert all(len(r) == W for r in g), [len(r) for r in g]
    return g


def blink(g):
    g = [r[:] for r in g]
    for y in (5, 6, 7, 8):
        for x in range(15, 19):
            if g[y][x] in "EW":
                g[y][x] = "b"
    g[6][16] = "E"
    g[6][17] = "E"
    g[7][15] = "E"
    g[7][18] = "E"
    return g


def squash(g):
    """body sinks 1px toward planted feet; wing tips spread"""
    top = [r[:] for r in g[:20]]
    out = [["."] * W] + top[:-1]  # shift rows 0..19 down by one, drop row 19 (tail tip)
    out[19] = top[19][:]
    out[19][0] = "."
    return out + [r[:] for r in g[20:]]


def to_img(g, pad_top=1):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    P = img.load()
    for y, row in enumerate(g):
        for x, ch in enumerate(row):
            if ch != "." and y + pad_top < H:
                P[x, y + pad_top] = COL[ch] + (255,)
    # close any outline gaps automatically
    filled = lambda x, y: 0 <= x < W and 0 <= y < H and P[x, y][3] and P[x, y][:3] != COL["o"]
    fix = []
    for y in range(H):
        for x in range(W):
            if P[x, y][3] == 0 and any(
                filled(x + dx, y + dy) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
            ):
                fix.append((x, y))
    for x, y in fix:
        P[x, y] = COL["o"] + (255,)
    return img


base = grid(BASE)
A = to_img(base)
S = to_img(squash(base), pad_top=1)
BL = to_img(blink(base))
frames = [A, A, S, S, A, A, BL, A]

sheet = Image.new("RGBA", (W * len(frames), H), (0, 0, 0, 0))
for i, f in enumerate(frames):
    sheet.paste(f, (i * W, 0))
sheet.save("lori_idle.png")
A.save("lori.png")


# previews
def prev(img, s=14, name="preview.png"):
    big = img.resize((img.width * s, img.height * s), Image.NEAREST)
    bg = Image.new("RGBA", big.size, (11, 14, 26, 255))
    bg.alpha_composite(big)
    bg.save(name)


prev(A)
row = Image.new("RGBA", (W * 3 + 8, H), (0, 0, 0, 0))
for i, f in enumerate([A, S, BL]):
    row.paste(f, (i * (W + 4), 0))
prev(row, 8, "frames.png")
frames_gif = [Image.new("RGBA", (W, H), (11, 14, 26, 255)) for _ in frames]
for bg, f in zip(frames_gif, frames):
    bg.alpha_composite(f)
gif = [
    f.resize((W * 12, H * 12), Image.NEAREST).convert("P", palette=Image.ADAPTIVE)
    for f in frames_gif
]
gif[0].save("lori_idle.gif", save_all=True, append_images=gif[1:], duration=140, loop=0, disposal=2)
print("ok")
