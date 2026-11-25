# Lorikeet art kit: dusk background, sparkles, landing dust. Verbatim except output paths (./out).
# Run after hand.py and word.py: uv run --with pillow python tools/sprites/scene.py
import os
import pathlib

OUT = pathlib.Path(__file__).parent / "out"
OUT.mkdir(exist_ok=True)
os.chdir(OUT)

from PIL import Image
import math

S = 10  # every effect shares Lori's 10x grid
GW, GH = 120, 76  # 1200 x 760 board in grid cells
BAYER = [[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]
TONES = [(11, 14, 26), (20, 17, 40), (36, 20, 48), (58, 26, 52)]  # night -> warm dusk glow

bg = Image.new("RGB", (GW, GH), TONES[0])
P = bg.load()
cx, cy, r = 60, 22, 26
for y in range(GH):
    for x in range(GW):
        d = math.hypot((x - cx), (y - cy) * 1.15)
        v = max(0.0, 1 - d / r) * (len(TONES) - 1)  # 0..3
        lo = int(v)
        frac = v - lo
        t = lo + (1 if frac * 16 > BAYER[y % 4][x % 4] + 0.5 else 0)
        P[x, y] = TONES[min(t, 3)]
# a few fixed stars, single pixels
for x, y, c in [
    (14, 9, (150, 140, 210)),
    (101, 13, (255, 244, 230)),
    (26, 55, (255, 217, 90)),
    (93, 47, (111, 168, 255)),
    (8, 40, (120, 110, 180)),
    (112, 62, (180, 140, 255)),
    (40, 70, (120, 110, 180)),
]:
    P[x, y] = c
bg.resize((GW * S, GH * S), Image.NEAREST).save("scene_bg.png")


# twinkle sparkle, 5x5, 8 frames
def sparkle(col, hi):
    shapes = [
        [],
        [(2, 2)],
        [(2, 2), (1, 2), (3, 2), (2, 1), (2, 3)],
        [(2, 2, "h"), (1, 2), (3, 2), (2, 1), (2, 3), (0, 2), (4, 2), (2, 0), (2, 4)],
        [(2, 2, "h"), (1, 2), (3, 2), (2, 1), (2, 3)],
        [(2, 2)],
        [],
        [],
    ]
    sh = Image.new("RGBA", (5 * len(shapes), 5), (0, 0, 0, 0))
    Q = sh.load()
    for i, s in enumerate(shapes):
        for p in s:
            Q[i * 5 + p[0], p[1]] = (hi if len(p) == 3 else col) + (255,)
    return sh


for name, col, hi in [
    ("spark_y", (255, 217, 90), (255, 250, 220)),
    ("spark_b", (111, 168, 255), (220, 235, 255)),
    ("spark_v", (180, 140, 255), (240, 230, 255)),
]:
    sparkle(col, hi).save(name + ".png")

# landing dust on Lori's squash frames (sheet frames 2 and 3)
sheet = Image.open("lori_idle.png").convert("RGBA")
Q = sheet.load()
DUST, DUST2 = (120, 110, 170, 255), (80, 72, 130, 255)
for x, y, c in [(9, 23, DUST), (20, 23, DUST)]:
    Q[2 * 24 + x, y] = c
for x, y, c in [(8, 22, DUST2), (21, 22, DUST2), (7, 23, DUST2), (22, 23, DUST2)]:
    Q[3 * 24 + x, y] = c
sheet.save("lori_idle_fx.png")

# preview composite (frame 3) for my own check
prev = bg.resize((GW * S, GH * S), Image.NEAREST).convert("RGBA")
f = sheet.crop((3 * 24, 0, 4 * 24, 24)).resize((240, 240), Image.NEAREST)
prev.alpha_composite(f, (480, 100))
n = Image.open("note.png").resize((220, 50), Image.NEAREST)
prev.alpha_composite(n, (520, 340))
w = Image.open("wordmark.png").resize((490, 90), Image.NEAREST)
prev.alpha_composite(w, (360, 440))
sp = Image.open("spark_y.png").crop((15, 0, 20, 5)).resize((50, 50), Image.NEAREST)
prev.alpha_composite(sp, (360, 170))
prev.save("scene_prev.png")
print("ok")
