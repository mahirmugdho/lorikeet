# 0009. Draw the clay look with Panda3D

- **Status:** Accepted
- **Date:** 2026-11-28
- **Deciders:** Ryan, Mahir

## Context

ADR 0008 lets a player pick how a game is drawn. The look we want next is a stop-motion clay set filmed under a softbox: chunky figures with soft shading, soft shadows that touch, and real notes casting shadows onto the set. That needs real 3D: lights, a shadow map, anti-aliasing and our own shaders, at 60 frames a second at projector resolution on a laptop's integrated graphics, from Python and with no build step. ADR 0002's stack (pygame-ce, pymunk, OpenCV) draws in 2D only.

## Options considered

1. **Panda3D.** A Python-first 3D engine with shadow-mapped lights, GLSL shaders that get the lights and shadow maps as inputs, offscreen rendering (for screenshots and look-dev without a window) and multisampling. It has wheels for Python 3.13 (about 53 MB). Cons: it owns its window and event loop, so its input has to be passed back as pygame events. On Linux it only draws through X11, which XWayland stretches on a scaled desktop, and once its window is open an SDL window on Wayland can't share the process.
2. **moderngl in the pygame window.** A thin OpenGL wrapper that draws into the window SDL already has, with one window system and one event loop. Cons: everything else is ours to write and keep working: the shadow pass, cameras, a scene graph and buffers.
3. **A separate engine (Godot, Blender) in its own process.** The best tools. Cons: a second runtime and language, the View sent over a socket each frame, and far more to install and ship.
4. **Clay sprites rendered ahead of time, drawn by pygame.** No 3D at runtime. Cons: no real shadows from real notes and no light changes, and poses, rolling and boil all become big sprite sheets.

## Decision

We will draw the clay look with Panda3D (`--renderer clay`), because it gives us shadow mapping, shaders and offscreen rendering without writing an engine, from the same Python process.

- Figures are modelled as signed distance functions and meshed with numpy (`render/clay/`), so modelling adds no dependency.
- Panda3D is imported only when the clay renderer is picked. The other renderers never load it.
- On Linux the clay renderer draws through X11, and with it the desk window's pygame does too. The set is drawn into an offscreen picture the canvas's size and stretched to the window, so a stretching desktop costs a stretch, not 2.25 times the drawing.

## Consequences

- Easier: lighting and shadows that read as a real set; offscreen screenshots for look-dev; one Python process, as ADR 0002 wants.
- Harder: everyone installs a 53 MB package. CI has no GPU, so only the parts that don't draw are tested there (meshes, the View-to-set sync, the window plumbing); the drawing is checked by eye and by frame times. With clay, both desk windows go through XWayland, so on a scaled laptop screen they open smaller than with the flat renderer.
- We're now committed to: Panda3D's shader inputs for lights and shadow maps, its X11 window on Linux, and `xrandr` to find the projector (so clay's projector output is Linux-only for now).
- Measured on the laptop's Intel graphics, at 1920x1080 with the desk window open: 16.2 ms between frames (60 fps), 0 late frames in 1078.
