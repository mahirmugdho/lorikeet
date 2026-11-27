"""Look development: Lori alone on the clay set, to get the look right before the game.

    uv run python -m lorikeet.render.clay.lookdev shots/    # offscreen screenshots
    uv run python -m lorikeet.render.clay.lookdev --time    # frame times in a window
    uv run python -m lorikeet.render.clay.lookdev --time --offscreen   # true GPU frame times

Screenshots are rendered offscreen (no window, through EGL) at the projector's resolution:

- `full.png`: the whole 1920x1080 frame, with Lori at the size she is in the game.
- `actual.png`: the part of that frame around Lori, blown up 4x with no smoothing, so you
  can judge her real pixels: edges, aliasing, how much texture survives at game size.
- `closeup.png`: the same set seen 10x closer, to judge the clay itself.

`--time` opens a real window instead, turns Lori slowly with the boil on, and reports the
average, 95th percentile and worst frame time, which is what has to stay under 16.7 ms. A
window can't go faster than the screen refreshes, so on a 120 Hz laptop every frame reads
8.3 ms however quick it really was. `--time --offscreen` renders offscreen and makes the GPU
finish each frame before the next (Panda3D's `gl-finish`), so it measures the real cost.
"""

from __future__ import annotations

import argparse
import math
import time
from pathlib import Path

import numpy as np
from panda3d.core import Filename, NodePath, PNMImage, loadPrcFileData

from lorikeet.render.clay.coords import to_world
from lorikeet.render.clay.detail import clay_detail
from lorikeet.render.clay.figure import build
from lorikeet.render.clay.lori import lori

SIZE = (1920, 1080)
CENTRE = (960.0, 560.0)
TURN = (-32.0, 12.0)
"""Lori's pose for the camera: turned 32 degrees to face us a little (so both her face and
her side show, like the reference's three-quarter views) and tipped 12 degrees towards us,
as if the camera were slightly above her."""

BOIL_RATE = 12.0
"""Boil steps per second: stop-motion is usually shot "on twos", 12 new frames a second."""


def main() -> None:
    parser = argparse.ArgumentParser(description="Lori alone on the clay set, for look-dev.")
    parser.add_argument("out", nargs="?", type=Path, default=Path(".lorikeet/lookdev"))
    parser.add_argument("--time", action="store_true", help="time frames in a window")
    parser.add_argument("--offscreen", action="store_true", help="with --time: no window")
    parser.add_argument("--size", type=int, nargs=2, default=SIZE, metavar=("W", "H"))
    parser.add_argument("--step", type=float, default=0.5, help="mesh grid step, in pixels")
    parser.add_argument("--frames", type=int, default=600)
    args = parser.parse_args()
    size = (args.size[0], args.size[1])
    window = args.time and not args.offscreen

    loadPrcFileData(
        "lookdev",
        f"""
        win-size {size[0]} {size[1]}
        window-title Lorikeet clay look-dev
        framebuffer-multisample 1
        multisamples 8
        sync-video {0 if args.time else 1}
        load-display {"pandagl" if window else "p3headlessgl"}
        gl-finish {1 if args.time and args.offscreen else 0}
        audio-library-name null
        textures-power-2 none
        show-frame-rate-meter {1 if window else 0}
        """,
    )
    from direct.showbase.ShowBase import ShowBase

    from lorikeet.render.clay.stage import Light, Stage, figure_node

    started = time.perf_counter()
    mesh = build(lori(), step=args.step)
    built = time.perf_counter()
    detail = clay_detail()
    textured = time.perf_counter()
    print(
        f"Lori: {len(mesh.positions)} vertices, {len(mesh.triangles)} triangles, "
        f"built in {built - started:.1f} s; detail texture in {textured - built:.1f} s"
    )

    base = ShowBase(windowType="onscreen" if window else "offscreen")
    base.disableMouse()
    assert base.win is not None, "Panda3D couldn't open a window or offscreen buffer"
    print(f"framebuffer: {base.win.getFbProperties()}")
    stage = Stage(base, size, detail, Light())
    tilt = stage.root.attachNewNode("lori tilt")
    tilt.setPos(*to_world(CENTRE))
    tilt.setP(TURN[1])
    figure = figure_node(mesh, "lori")
    figure.reparentTo(tilt)
    figure.setH(TURN[0])

    if args.time:
        _time(base, stage, figure, args.frames)
    else:
        _shoot(base, args.out, size)


def _shoot(base, out: Path, size: tuple[int, int]) -> None:
    from lorikeet.render.clay.stage import canvas_camera, close_up

    out.mkdir(parents=True, exist_ok=True)
    full = _render(base, *canvas_camera(size))
    full.write(Filename.fromOsSpecific(str(out / "full.png")))
    # Lori at her real pixels, blown up without smoothing.
    crop_w, crop_h = 240, 135
    x0, y0 = int(CENTRE[0] - crop_w / 2), int(CENTRE[1] - crop_h / 2)
    crop = PNMImage(crop_w * 4, crop_h * 4)
    for y in range(crop_h * 4):
        for x in range(crop_w * 4):
            crop.setXel(x, y, full.getXel(x0 + x // 4, y0 + y // 4))
    crop.write(Filename.fromOsSpecific(str(out / "actual.png")))
    close = _render(base, *close_up(size, CENTRE, zoom=10))
    close.write(Filename.fromOsSpecific(str(out / "closeup.png")))
    print(f"wrote {out / 'full.png'}, {out / 'actual.png'} and {out / 'closeup.png'}")


def _render(base, lens, place) -> PNMImage:
    base.cam.node().setLens(lens)
    base.cam.setPos(place)
    # Twice: the first frame also renders the shadow map for the first time.
    base.graphicsEngine.renderFrame()
    base.graphicsEngine.renderFrame()
    image = PNMImage()
    base.win.getScreenshot(image)
    return image


def _time(base, stage, figure: NodePath, frames: int) -> None:
    """Turn Lori slowly with the boil on, and time every frame."""
    times = []
    start = last = time.perf_counter()
    figure.setShaderInput("boil_amount", 0.3)
    for frame in range(frames + 30):
        now = time.perf_counter()
        t = now - start
        figure.setH(TURN[0] + 25 * math.sin(t * 0.7))
        figure.setShaderInput("boil_seed", float(math.floor(t * BOIL_RATE)))
        base.graphicsEngine.renderFrame()
        if frame >= 30:  # skip warm-up: shader compiles, first shadow map
            times.append(now - last)
        last = now
    ms = np.array(times[1:]) * 1000
    width, height = base.win.getXSize(), base.win.getYSize()
    print(
        f"{len(ms)} frames at {width}x{height}: average {ms.mean():.2f} ms, "
        f"p95 {np.percentile(ms, 95):.2f} ms, worst {ms.max():.2f} ms "
        f"({1000 / ms.mean():.0f} fps)"
    )


if __name__ == "__main__":
    main()
