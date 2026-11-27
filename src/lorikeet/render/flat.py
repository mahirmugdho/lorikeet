"""The flat renderer: draws a View in flat 2D shapes with pygame-ce.

It opens and owns the window (ADR 0008). The window is either on this screen, scaled to fit
however big it is, or fullscreen on the projector at the projector's own resolution. Either
way the canvas is in projector pixels.

It asks each system for the display's own pixels, so the desktop doesn't stretch the picture
(see `native_pixel_settings`). Alignment with real notes doesn't depend on that, because
calibration measures wherever the canvas lands, but a stretched picture is softer and costs
more pixels to draw.

What each kind of thing looks like comes from a set of looks: `flat_looks` by default. The
sketch renderer is this same window with pencil looks (`sketch`).
"""

from __future__ import annotations

import os
import sys
from collections.abc import Mapping, Sequence
from typing import Protocol

import pygame

from lorikeet.render.flat_looks import BACKDROP as BACKDROP  # where it's defined
from lorikeet.render.flat_looks import FlatLooks
from lorikeet.view import Thing, View


class Looks(Protocol):
    """What each kind of thing looks like, for a pygame window: a background colour, and a
    way to draw one thing."""

    @property
    def backdrop(self) -> tuple[int, int, int]: ...

    def draw(self, canvas: pygame.Surface, thing: Thing) -> None: ...


class FlatRenderer:
    def __init__(
        self, output: str, size: tuple[int, int], display: int, looks: Looks | None = None
    ) -> None:
        """Open the window: `output` is "window" (a `size` canvas in a window on this
        screen) or "projector" (fullscreen on display number `display`). `looks` draws
        each thing (flat looks unless given)."""
        # By default SDL minimises a fullscreen window when it loses focus, so clicking on
        # the laptop screen would make the projector go blank.
        os.environ.setdefault("SDL_VIDEO_MINIMIZE_ON_FOCUS_LOSS", "0")
        chosen = native_pixel_settings(os.environ, sys.platform)
        os.environ.update(chosen)
        pygame.display.quit()  # if it was already open with other settings, start it again
        try:
            pygame.display.init()
        except pygame.error:
            if "SDL_VIDEODRIVER" not in chosen:
                raise
            del os.environ["SDL_VIDEODRIVER"]  # this SDL can't use Wayland: use its default
            pygame.display.init()
        pygame.display.set_caption("Lorikeet")
        self._canvas = _open_projector(display) if output == "projector" else _open_window(size)
        self._looks: Looks = looks if looks is not None else FlatLooks()

    @property
    def size(self) -> tuple[int, int]:
        return self._canvas.get_size()

    def events(self) -> list[pygame.event.Event]:
        return pygame.event.get()

    def draw(self, view: View, wall: pygame.Surface, layer: pygame.Surface) -> None:
        self._canvas.fill(self._looks.backdrop)
        for thing in view.back_to_front():
            self._looks.draw(self._canvas, thing)
        # The picture lands on what's on the wall (see Renderer): white leaves it as it is.
        self._canvas.blit(wall, (0, 0), special_flags=pygame.BLEND_MULT)
        # What's in front of the wall, laid on top as it is. It's premultiplied (see Renderer).
        self._canvas.blit(layer, (0, 0), special_flags=pygame.BLEND_PREMULTIPLIED)
        pygame.display.flip()

    def close(self) -> None:
        pygame.display.quit()


def native_pixel_settings(environ: Mapping[str, str], platform: str) -> dict[str, str]:
    """SDL settings that give the window the display's own pixels, on any setup.

    - Linux in a Wayland session: SDL's Wayland driver. Through X11 (XWayland), a desktop
      with display scaling on any screen can stretch every X11 window, the projector's
      included (2880x1620 drawn, shrunk to a 1920x1080 projector). Through Wayland the
      projector's window gets its own pixels.
    - Windows: declare the app aware of display scaling, so Windows doesn't stretch it.

    Settings already in `environ` are kept, so `SDL_VIDEODRIVER=x11` still wins.
    """
    settings: dict[str, str] = {}
    if platform.startswith("linux") and environ.get("WAYLAND_DISPLAY"):
        settings["SDL_VIDEODRIVER"] = "wayland"
    if platform == "win32":
        settings["SDL_WINDOWS_DPI_AWARENESS"] = "permonitorv2"
    return {key: value for key, value in settings.items() if key not in environ}


def stretch_warning(
    display: int, desktop: tuple[int, int], modes: Sequence[tuple[int, int]]
) -> str | None:
    """A warning if the desktop gives `display` fewer pixels than it can show, which usually
    means the display is set to scale above 100%. Through Wayland the desktop size is the
    scaled one, so this catches it. Through X11 (XWayland) both numbers come back stretched
    alike, so it can't, which is one more reason to draw through Wayland."""
    if not modes or modes[0] == desktop:
        return None
    (width, height), (most_w, most_h) = desktop, modes[0]
    return (
        f"lorikeet: display {display} is drawn at {width}x{height} but can show "
        f"{most_w}x{most_h}. If it's set to scale above 100%, set it to 100% for a sharp, "
        "full-resolution picture."
    )


def _open_window(size: tuple[int, int]) -> pygame.Surface:
    # SCALED keeps the canvas at `size` however big the window is, and maps mouse positions
    # back onto the canvas, so everything stays in projector pixels.
    return pygame.display.set_mode(size, pygame.SCALED | pygame.RESIZABLE)


def _open_projector(display: int) -> pygame.Surface:
    sizes = pygame.display.get_desktop_sizes()
    if display >= len(sizes):
        raise SystemExit(
            f"lorikeet: no display {display}, only {len(sizes)}: {sizes}. Is the projector "
            "plugged in, and set to extend the desktop rather than mirror it?"
        )
    modes = pygame.display.list_modes(display=display)
    modes = modes if isinstance(modes, list) else []  # -1 means "any size", so no list
    if (warning := stretch_warning(display, sizes[display], modes)) is not None:
        print(warning, file=sys.stderr)
    pygame.display.set_mode(sizes[display], display=display)
    # Fullscreen at the desktop's own resolution, so one canvas pixel is one projector pixel.
    # The other kind (desktop=False) changes the video mode, which can rescale the picture.
    pygame.Window.from_display_module().set_fullscreen(desktop=True)
    canvas = pygame.display.get_surface()  # fetched again, as going fullscreen can replace it
    if canvas is None:
        raise SystemExit("lorikeet: the projector window closed as it went fullscreen")
    return canvas
