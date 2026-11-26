# Lorikeet art kit: wordmark and the yellow sticky note. Verbatim except output paths (now ./out).
# Run: uv run --with pillow python tools/sprites/word.py
import os
import pathlib

OUT = pathlib.Path(__file__).parent / "out"
OUT.mkdir(exist_ok=True)
os.chdir(OUT)

from PIL import Image

G = {
    "l": ["#..", "#..", "#..", "#..", "#..", "#..", "#..", ".##"],
    "o": [".....", ".....", ".....", ".###.", "#...#", "#...#", "#...#", ".###."],
    "r": ["....", "....", "....", "#.##", "##..", "#...", "#...", "#..."],
    "i": ["SS", "SD", "..", "#.", "#.", "#.", "#.", ".#"],
    "k": ["#...", "#...", "#...", "#..#", "#.#.", "##..", "#.#.", "#..#"],
    "e": [".....", ".....", ".....", ".###.", "#...#", "#####", "#....", ".###."],
    "t": ["....", ".#..", ".#..", "####", ".#..", ".#..", ".#..", "..##"],
}
CREAM = (255, 244, 230)
PEACH = (255, 206, 184)
SH = (58, 46, 110)
S = (255, 217, 90)
D = (214, 160, 40)
word = "lorikeet"
w = sum(len(G[c][0]) + 1 for c in word) + len(word) - 1
img = Image.new("RGBA", (w + 2, 9), (0, 0, 0, 0))
P = img.load()
x0 = 0
cells = []
for c in word:
    g = G[c]
    for y, row in enumerate(g):
        for x, ch in enumerate(row):
            if ch == "#":
                cells.append((x0 + x, y, ch))
                cells.append((x0 + x + 1, y, ch))
            elif ch != ".":
                cells.append((x0 + x + (1 if ch in "SD" else 0), y, ch))
    x0 += len(g[0]) + 2
for x, y, ch in cells:  # shadow first
    if ch == "#":
        P[x + 1, y + 1] = SH + (255,)
for x, y, ch in cells:
    if ch == "#":
        P[x, y] = (CREAM if y < 6 else PEACH) + (255,)
    elif ch == "S":
        P[x, y] = S + (255,)
    elif ch == "D":
        P[x, y] = D + (255,)
img.save("wordmark.png")
# a little yellow sticky note for Lori to stand on (20 x 5)
n = Image.new("RGBA", (22, 5), (0, 0, 0, 0))
N = n.load()
for x in range(1, 21):
    N[x, 0] = (255, 236, 150, 255)
    N[x, 1] = (255, 217, 90, 255)
    N[x, 2] = (255, 217, 90, 255)
    N[x, 3] = (214, 160, 40, 255)
N[20, 0] = (0, 0, 0, 0)
N[19, 0] = (214, 160, 40, 255)
N[20, 1] = (214, 160, 40, 255)  # curled corner
for x in range(2, 21):
    N[x, 4] = (40, 30, 70, 255)
n.save("note.png")
big = img.resize((img.width * 14, img.height * 14), Image.NEAREST)
bg = Image.new("RGBA", (big.width + 40, big.height + 40), (11, 14, 26, 255))
bg.alpha_composite(big, (20, 20))
bg.save("word_prev.png")
print(img.size)
