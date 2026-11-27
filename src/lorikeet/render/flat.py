"""The flat renderer: draws a View in flat 2D shapes with pygame-ce.

It opens and owns the window (ADR 0008). The window is either on this screen, scaled to fit
however big it is, or fullscreen on the projector at the projector's own resolution. Either
way the canvas is in projector pixels.

For now every kind of thing gets the same plain look. Real looks per kind (soft colours,
rounded shapes, light shadows) come with the first game, once there are kinds to draw.
"""

from __future__ import annotations

import os

import pygame

from lorikeet.view import Circle, Thing, View

BACKDROP = (232, 230, 226)
"""A light, nearly grey backdrop: shadows show on it, and it adds almost no colour to real
notes under the projector, because detection keys on saturation (ADR 0006)."""

DEFAULT_FILL = (150, 146, 140)
DEFAULT_EDGE = (105, 101, 96)
"""The plain look for kinds without one of their own."""


class FlatRenderer:
    def __init__(self, output: str, size: tuple[int, int], display: int) -> None:
        """Open the window: `output` is "window" (a `size` canvas in a window on this
        screen) or "projector" (fullscreen on display number `display`)."""
        # By default SDL minimises a fullscreen window when it loses focus, so clicking on
        # the laptop screen would make the projector go blank.
        os.environ.setdefault("SDL_VIDEO_MINIMIZE_ON_FOCUS_LOSS", "0")
        pygame.display.init()
        pygame.display.set_caption("Lorikeet")
        self._canvas = _open_projector(display) if output == "projector" else _open_window(size)

    @property
    def size(self) -> tuple[int, int]:
        return self._canvas.get_size()

    def events(self) -> list[pygame.event.Event]:
        return pygame.event.get()

    def draw(self, view: View, layer: pygame.Surface) -> None:
        self._canvas.fill(BACKDROP)
        for thing in view.back_to_front():
            _draw_thing(self._canvas, thing)
        # The overlays, laid on top as they are. The layer is premultiplied (see Renderer).
        self._canvas.blit(layer, (0, 0), special_flags=pygame.BLEND_PREMULTIPLIED)
        pygame.display.flip()

    def close(self) -> None:
        pygame.display.quit()


def _draw_thing(canvas: pygame.Surface, thing: Thing) -> None:
    if isinstance(thing.shape, Circle):
        pygame.draw.circle(canvas, DEFAULT_FILL, thing.position, thing.shape.radius)
        pygame.draw.circle(canvas, DEFAULT_EDGE, thing.position, thing.shape.radius, 2)
    else:
        points = thing.shape.placed(thing.position, thing.angle)
        pygame.draw.polygon(canvas, DEFAULT_FILL, points)
        pygame.draw.polygon(canvas, DEFAULT_EDGE, points, 2)


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
    pygame.display.set_mode(sizes[display], display=display)
    # Fullscreen at the desktop's own resolution, so one canvas pixel is one projector pixel.
    # The other kind (desktop=False) changes the video mode, which can rescale the picture.
    pygame.Window.from_display_module().set_fullscreen(desktop=True)
    canvas = pygame.display.get_surface()  # fetched again, as going fullscreen can replace it
    if canvas is None:
        raise SystemExit("lorikeet: the projector window closed as it went fullscreen")
    return canvas
