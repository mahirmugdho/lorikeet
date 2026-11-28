"""The clay renderer: a game's View as a stop-motion clay set, drawn with Panda3D.

    uv run lorikeet --renderer clay                     # at the desk
    uv run lorikeet --renderer clay --output projector  # on the wall

It's a renderer like the others (`lorikeet.render.Renderer`): the launcher hands it the
game's View, the wall and the overlay layer each frame, and it owns its window. Inside:

- **The set** (`stage.py`, `scene.py`): every thing in the View gets its clay figure, put
  where the View says, posed and boiled at 12 frames a second (`motion.py`).
- **Figures are built in the background** (`builder.py`), so the first egg doesn't freeze the
  game while it's built. Until a figure is ready its thing is left out. At startup the whole
  set is held out of sight until it's all there, then shown at once (`loading.py`), with a
  loading screen of pre-rendered clay meanwhile if that takes a moment
  (`loading_screen.py`).
- **The canvas.** The set is drawn into an offscreen picture the canvas's own size (projector
  pixels, with 8x anti-aliasing), then the wall and the overlay layer go on top of it, in
  that order. (The game's words are clay letters on the set itself: `clayfont.py`.) The
  window just shows the finished picture, stretched to fill it. So the set costs the same
  however big the window is, even where the desktop gives an X11 window 2.25 times the
  projector's pixels (Panda3D draws through X11 on Linux).
- **Input.** The launcher speaks pygame; this window is Panda3D's. Its keys and its close
  button are turned into pygame events (`events`). F shows Panda3D's frame-rate meter.
- **Frame times.** On closing, it prints the average, 95th percentile and worst time between
  frames, which is what has to stay at 16.7 ms for 60 frames a second.
"""

from __future__ import annotations

import os
import sys
import time
from collections.abc import Sequence
from types import SimpleNamespace

import numpy as np
import pygame
from panda3d.core import (
    Camera,
    CardMaker,
    ColorBlendAttrib,
    FrameBufferProperties,
    GraphicsOutput,
    GraphicsPipe,
    NodePath,
    OrthographicLens,
    SamplerState,
    Texture,
    TextureStage,
    WindowProperties,
    loadPrcFileData,
)

from lorikeet.render.clay.builder import Builder
from lorikeet.render.clay.cache import detail
from lorikeet.render.clay.loading import Loading
from lorikeet.render.clay.loading_screen import LoadingScreen
from lorikeet.render.clay.mirror import FLIPPED, Mirror
from lorikeet.render.clay.motion import frame_of
from lorikeet.render.clay.scene import ClayScene
from lorikeet.render.clay.stage import Light, Stage
from lorikeet.render.clay.window import fit, letterbox, monitors, pygame_key, pygame_settings
from lorikeet.view import View

TITLE = "Lorikeet"
LETTERBOX = (60 / 255, 58 / 255, 54 / 255, 1.0)
"""Behind the canvas where the window's shape doesn't match it (as in the desk window)."""

MULTISAMPLES = 8


class ClayRenderer:
    def __init__(self, output: str, size: tuple[int, int], display: int) -> None:
        """Open the window: `output` is "window" (the `size` canvas in a window on this
        screen, shrunk if the screen is smaller) or "projector" (the whole of display number
        `display`, with no border)."""
        self._size = size
        _start_pygame_display()  # the overlays and the desk window still draw with pygame
        origin, window_size, bare = _placement(output, size, display)
        loadPrcFileData(
            "lorikeet clay",
            f"""
            window-title {TITLE}
            win-size {window_size[0]} {window_size[1]}
            {f"win-origin {origin[0]} {origin[1]}" if origin else ""}
            undecorated {1 if bare else 0}
            load-display pandagl
            sync-video 1
            framebuffer-multisample 0
            audio-library-name null
            textures-power-2 none
            """,
        )
        from direct.showbase.ShowBase import ShowBase  # reads the settings above

        base = ShowBase()
        base.disableMouse()
        if base.win is None or base.camNode is None or base.buttonThrowers is None:
            raise SystemExit("lorikeet: Panda3D couldn't open a window for the clay renderer")
        self._base = base
        # The window doesn't draw the set itself: it shows the finished canvas (below).
        base.camNode.setActive(False)
        base.win.setClearColor(LETTERBOX)

        buffer, canvas = _canvas(base, size)
        camera = base.makeCamera(buffer, camName="clay camera")
        layer2d = _layer2d(buffer)
        stage = Stage(
            SimpleNamespace(render=base.render, cam=camera, render2d=layer2d),
            size,
            detail(),
            Light(),
        )
        self._builder = Builder()
        self._scene = ClayScene(stage, self._builder, new_per_frame=1, prefetch_font=True)
        self._loading_screen = LoadingScreen(layer2d, size)
        self._loading_screen_root = layer2d.find("loading screen")
        self._loading_screen_root.setBin("fixed", 10)
        # On top of the set, in order: the loading screen (while there is one), then the
        # wall (the picture lands on the paper), then the overlay layer.
        self._wall = Mirror("wall", size, every=4)
        wall_card = stage.wall_layer()
        wall_card.setTexture(self._wall.texture)
        _flip(wall_card)
        wall_card.setBin("fixed", 20)
        self._layer = Mirror("layer", size, every=2)
        self._layer_card = _layer_card(layer2d, self._layer.texture)

        maker = CardMaker("canvas")
        maker.setFrameFullscreenQuad()
        self._shown = base.render2d.attachNewNode(maker.generate())
        self._shown.setTexture(canvas)
        self._fit_window()

        self._inbox: list[pygame.event.Event] = []
        base.buttonThrowers[0].node().setButtonDownEvent("clay-button")
        base.accept("clay-button", self._on_button)
        base.win.setCloseRequestEvent("clay-close")  # closing asks, rather than just closing
        base.accept("clay-close", self._on_close)
        base.accept("window-event", self._on_window_event)  # in place of ShowBase's own
        self._meter = False
        self._started = time.monotonic()
        self._loading = Loading(self._started)
        self._scene.hold(True)  # until it has all loaded
        self._frames: list[float] = []

    @property
    def size(self) -> tuple[int, int]:
        return self._size

    def events(self, pending: Sequence[pygame.event.Event]) -> list[pygame.event.Event]:
        """This window's input since the last call, as pygame events. `pending` is pygame's
        own input, from the other windows, so it's left alone."""
        mine, self._inbox = self._inbox, []
        return mine

    def draw(self, view: View, wall: pygame.Surface, layer: pygame.Surface) -> None:
        now = time.monotonic()
        self._frames.append(now)
        self._scene.show(view, now - self._started)
        progress = self._loading.step(self._scene.missing, now, self._scene.progress())
        self._scene.hold(progress.holding)
        # Pictures rendered ahead of time (`loading_art.py`): nothing to load itself.
        self._loading_screen.show(progress.screen, progress.beads, frame_of(now - self._started))
        self._wall.update(wall)
        self._layer.update(layer)
        if self._layer.empty:
            self._layer_card.hide()  # nothing to lay on: skip a full-screen pass
        else:
            self._layer_card.show()
        # One step of Panda3D's own loop: draw the canvas, then the window, and read input.
        self._base.taskMgr.step()

    def close(self) -> None:
        self._report()
        self._builder.close()
        self._base.destroy()

    def _fit_window(self) -> None:
        """Stretch the canvas over the window, keeping its shape."""
        assert self._base.win is not None
        props = self._base.win.getProperties()
        across, up = letterbox((props.getXSize(), props.getYSize()), self._size)
        self._shown.setScale(across, 1, up)

    def _on_button(self, button: str) -> None:
        key = pygame_key(button)
        if key is None:
            return
        if key == pygame.K_f:
            self._meter = not self._meter
            self._base.setFrameRateMeter(self._meter)
        name = pygame.key.name(key)
        self._inbox.append(
            pygame.event.Event(
                pygame.KEYDOWN, key=key, mod=0, unicode=name if len(name) == 1 else ""
            )
        )

    def _on_close(self) -> None:
        self._inbox.append(pygame.event.Event(pygame.WINDOWCLOSE))

    def _on_window_event(self, window) -> None:
        if window is not self._base.win:
            return
        if not window.getProperties().getOpen():
            self._on_close()
        else:
            self._fit_window()

    def _report(self) -> None:
        """The time between frames, ignoring the first second (shaders compiling, the
        figures arriving)."""
        gaps = np.diff(self._frames[60:]) * 1000
        if len(gaps) < 10:
            return
        late = int((gaps > 1.5 * 1000 / 60).sum())
        print(
            f"lorikeet: clay frames: average {gaps.mean():.1f} ms, 95th percentile "
            f"{np.percentile(gaps, 95):.1f} ms, worst {gaps.max():.1f} ms, {late} of "
            f"{len(gaps)} late (over 25 ms)"
        )


def _start_pygame_display() -> None:
    """Start pygame's display again for the desk window, set up to share the process with
    Panda3D (see `window.pygame_settings`)."""
    os.environ.update(pygame_settings(sys.platform))
    pygame.display.quit()
    pygame.display.init()


def _placement(
    output: str, size: tuple[int, int], display: int
) -> tuple[tuple[int, int] | None, tuple[int, int], bool]:
    """Where the window goes (None: wherever the desktop puts it), its size, and whether it
    has no border."""
    screens = monitors()
    if output == "projector":
        if display >= len(screens):
            found = ", ".join(f"{m.name} {m.width}x{m.height}" for m in screens) or "none"
            raise SystemExit(
                f"lorikeet: no display {display} for the clay renderer (found: {found}). Is "
                "the projector plugged in, and set to extend the desktop rather than mirror "
                "it? (The clay renderer finds displays with xrandr, so it needs X11 or "
                "XWayland.)"
            )
        screen = screens[display]
        return (screen.x, screen.y), (screen.width, screen.height), True
    primary = next((m for m in screens if m.primary), screens[0] if screens else None)
    area = (primary.width, primary.height) if primary else size
    return None, fit(size, area), False


def _canvas(base, size: tuple[int, int]):
    """An offscreen picture the canvas's size, anti-aliased, that the set is drawn into,
    and the texture it ends up in. It's drawn before the window (a lower sort)."""
    properties = FrameBufferProperties()
    properties.setRgbColor(True)
    properties.setRgbaBits(8, 8, 8, 8)
    properties.setDepthBits(24)
    properties.setMultisamples(MULTISAMPLES)
    buffer = base.graphicsEngine.makeOutput(
        base.pipe,
        "clay canvas",
        -2,
        properties,
        WindowProperties.size(*size),
        GraphicsPipe.BFRefuseWindow,
        base.win.getGsg(),
        base.win,
    )
    if buffer is None:
        raise SystemExit("lorikeet: Panda3D couldn't make the clay renderer's canvas")
    texture = Texture("clay canvas")
    texture.setMinfilter(SamplerState.FT_linear)
    texture.setMagfilter(SamplerState.FT_linear)
    buffer.addRenderTexture(texture, GraphicsOutput.RTMBindOrCopy, GraphicsOutput.RTPColor)
    buffer.setClearColor((0, 0, 0, 1))
    return buffer, texture


def _layer2d(buffer) -> NodePath:
    """A 2D layer drawn onto the canvas after the set, spanning it from -1 to 1 both ways."""
    root = NodePath("clay canvas 2d")
    root.setDepthTest(False)
    root.setDepthWrite(False)
    lens = OrthographicLens()
    lens.setFilmSize(2, 2)
    lens.setNearFar(-1000, 1000)
    camera = Camera("clay canvas 2d camera", lens)
    region = buffer.makeDisplayRegion()
    region.setSort(10)  # after the set's (0)
    region.setCamera(root.attachNewNode(camera))
    return root


def _layer_card(root: NodePath, texture: Texture) -> NodePath:
    """The overlay layer: premultiplied, so it's laid on as source + picture x (1 - source
    alpha), the one blend that stays right where see-through things overlap."""
    maker = CardMaker("layer")
    maker.setFrameFullscreenQuad()
    maker.setUvRange(*FLIPPED)
    card = root.attachNewNode(maker.generate())
    card.setTexture(texture)
    card.setAttrib(
        ColorBlendAttrib.make(
            ColorBlendAttrib.M_add,
            ColorBlendAttrib.O_one,
            ColorBlendAttrib.O_one_minus_incoming_alpha,
        )
    )
    card.setBin("fixed", 30)
    return card


def _flip(card: NodePath) -> None:
    """Show a texture upside down, so pygame's top row (its first) is at the top."""
    card.setTexScale(TextureStage.getDefault(), 1, -1)
    card.setTexOffset(TextureStage.getDefault(), 0, 1)
